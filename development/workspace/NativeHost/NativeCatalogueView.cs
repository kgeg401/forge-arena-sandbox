using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using GreClient.CardData;
using Wizards.Mtga;
using Wizards.Mtga.PreferredPrinting;
using Wizards.Arena.Promises;
using Wotc.Mtga.Loc;

namespace ForgeArenaSandbox;

// Original three-page renderer, expansion flags, tag controls and animations.
// All owned Arena catalogue entries remain reachable; no 500-result cutoff.
public sealed class NativeCatalogueView
{
    private static readonly Dictionary<CardPoolHolder,NativeCatalogueView> Owners=new Dictionary<CardPoolHolder,NativeCatalogueView>();
    private static bool _patched;
    private readonly CardPoolHolder _pool;
    private readonly LocalPrintingPreferences _preferences;
    private readonly IPreferredPrintingDataProvider _provider;
    private readonly Dictionary<uint,CardPrintingData> _cards;
    private readonly Func<uint,bool> _preferred;
    private readonly Func<JObject> _deck;
    private readonly HashSet<uint> _expanded=new HashSet<uint>();
    private CardPrintingData[] _matched=Array.Empty<CardPrintingData>();
    private List<PagesMetaCardViewDisplayInformation> _display=new List<PagesMetaCardViewDisplayInformation>();
    public IReadOnlyList<uint> DisplayIds{get;private set;}=Array.Empty<uint>();
    public int TitleCount=>_matched.Select(c=>c.TitleId).Distinct().Count();
    public NativeCatalogueView(string path,PAPA papa,CardPoolHolder pool,IEnumerable<uint> ids,Func<uint,bool> preferred,Func<JObject> deck)
    {
        _pool=pool;_preferred=preferred;_deck=deck;
        _cards=ids.ToDictionary(id=>id,id=>papa.CardDatabase.CardDataProvider.GetCardPrintingById(id));
        _preferences=new LocalPrintingPreferences(path,_cards.ToDictionary(p=>p.Key,p=>p.Value.TitleId));_provider=new PrintingProvider(_preferences);
        Owners.Add(pool,this);
        if(!_patched)
        {
            var h=new Harmony("local.forge-arena.catalogue-printings");
            h.Patch(AccessTools.Method(typeof(CardPoolHolder),"CardExpansionToggled"),prefix:new HarmonyMethod(typeof(NativeCatalogueView),nameof(Expansion)));
            h.Patch(AccessTools.Method(typeof(CardPoolHolder),"CardPreferredPrintingToggleClicked"),prefix:new HarmonyMethod(typeof(NativeCatalogueView),nameof(Favorite)));
            h.Patch(AccessTools.Method(typeof(PagesMetaCardView),"UpdateDisplayInfo"),prefix:new HarmonyMethod(typeof(NativeCatalogueView),nameof(BeforeDisplay)));
            _patched=true;
        }
    }
    private static bool Expansion(CardPoolHolder __instance,PagesMetaCardView cardView)
    {
        if(!Owners.TryGetValue(__instance,out var owner))return true;
        if(!owner._expanded.Remove(cardView.TitleId))owner._expanded.Add(cardView.TitleId);
        owner.Render(false);__instance.ScrollForCollapsedIfNeeded(cardView);return false;
    }
    private static bool Favorite(CardPoolHolder __instance,PagesMetaCardView cardView,bool toggleValue)
    {
        if(!Owners.TryGetValue(__instance,out var owner))return true;
        owner._preferences.Set(cardView.TitleId,toggleValue?cardView.Card.GrpId:(uint?)null);owner.Render(false);return false;
    }
    private static void BeforeDisplay(PagesMetaCardView __instance)
    {
        if(__instance.Holder is CardPoolHolder pool && Owners.TryGetValue(pool,out var owner))AccessTools.Field(typeof(PagesMetaCardView),"_preferredPrintingDataProvider").SetValue(__instance,owner._provider);
    }
    public void SetCards(IEnumerable<CardPrintingData> matched,bool resetPage=true){_matched=matched.ToArray();Render(resetPage);}
    private void Render(bool resetPage)
    {
        var display=new List<PagesMetaCardViewDisplayInformation>();
        foreach(var group in _matched.GroupBy(c=>c.TitleId))
        {
            var saved=_preferences.Get(group.Key);
            var printings=group.OrderByDescending(c=>c.GrpId==saved).ThenByDescending(c=>_preferred(c.GrpId)).ThenByDescending(c=>c.GrpId).ToArray();
            bool expanded=_expanded.Contains(group.Key);var visible=expanded?printings:printings.Take(1);
            int index=0;foreach(var card in visible)
            {
                display.Add(new PagesMetaCardViewDisplayInformation{Card=card,Max=999,AvailablePrintingCount=999,AvailableTitleCount=999,RemainingTitleCount=999,QuantityStyle=PagesMetaCardView.QuantityDisplayStyle.Infinity,Skin=null!,ExpandedStyle=PreferredPrintingUtilities.ExpandedMode(index++,expanded,printings.Length)});
            }
        }
        _display=display;DisplayIds=display.Select(d=>d.Card.GrpId).ToArray();RefreshQuantities();if(resetPage)_pool.ScrollToTop();
        _pool.NoCardsText.text=Languages.ActiveLocProvider.GetLocalizedText("MainNav/Deckbuilder/NoFilteredCards/Default");_pool.NoCardsText.gameObject.SetActive(display.Count==0);
    }
    public void RefreshQuantities()
    {
        // Quantities do not change this sandbox's owned-card search metadata.
        // Reuse the filtered/expanded printing list instead of re-running the
        // database matcher, catalogue sort and printing grouping on every click.
        var deck=_deck();var used=new[]{"main","sideboard","commander","companion"}.SelectMany(p=>((JObject)deck[p]!).Properties()).GroupBy(p=>uint.Parse(p.Name)).ToDictionary(g=>g.Key,g=>(uint)g.Sum(p=>(int)p.Value));
        var titles=used.GroupBy(p=>_cards[p.Key].TitleId).ToDictionary(g=>g.Key,g=>(uint)g.Sum(p=>p.Value));
        foreach(var item in _display)
        {
            used.TryGetValue(item.Card.GrpId,out var count);titles.TryGetValue(item.Card.TitleId,out var titleCount);
            item.UsedPrintingCount=count;item.UsedTitleCount=titleCount;
        }
        _pool.SetCards(_display,false);
    }
    private sealed class Completed<T>:Promise<T>{public Completed(T value){Start();Complete(value);}}
    private sealed class PrintingProvider:IPreferredPrintingDataProvider
    {
        private readonly LocalPrintingPreferences _data;
        public PrintingProvider(LocalPrintingPreferences data){_data=data;}
        public IReadOnlyDictionary<int,PreferredPrintingWithStyle> GetAllPreferredPrintings()=>_data.Values.ToDictionary(p=>(int)p.Key,p=>new PreferredPrintingWithStyle{printingGrpId=(int)p.Value,styleCode=null!});
        public PreferredPrintingWithStyle GetPreferredPrintingForTitleId(int titleId)=>_data.Get((uint)titleId) is uint id?new PreferredPrintingWithStyle{printingGrpId=(int)id,styleCode=null!}:null!;
        public Promise<bool> SetPreferredPrintingForTitleId(int titleId,int grpId,string styleCode){if(!string.IsNullOrEmpty(styleCode))throw new NotSupportedException("Local card-style preferences are not enabled.");_data.Set((uint)titleId,(uint)grpId);return new Completed<bool>(true);}
        public Promise<bool> RemovePreferredPrintingForTitleId(int titleId){_data.Set((uint)titleId,null);return new Completed<bool>(true);}
        public Promise<Dictionary<int,PreferredPrintingWithStyle>> ForceRefreshPreferredPrintings()=>new Completed<Dictionary<int,PreferredPrintingWithStyle>>(GetAllPreferredPrintings().ToDictionary(p=>p.Key,p=>p.Value));
    }
}

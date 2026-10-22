using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Core.Code.Decks;
using Core.Shared.Code.CardFilters;
using GreClient.CardData;
using Wotc.Mtga.Cards.Database;

namespace ForgeArenaSandbox;

// Keep search and color semantics in the installed client's own evaluator.
// The context is private to this catalogue; no online deck services are used.
internal sealed class NativeCatalogueFilters
{
    private readonly CardDatabase _database;
    private readonly CardFilter _filter;
    private readonly CardMatcher.CardMatcherMetadata _metadata;
    public NativeCatalogueFilters(CardDatabase database,IEnumerable<uint> printingIds)
    {
        _database=database;
        var context=new DeckBuilderContextProvider(null!){Context=new DeckBuilderContext()};
        _filter=new CardFilter(database,new SetMetadataProvider(),context,null!);
        var printings=printingIds.Select(id=>database.CardDataProvider.GetCardPrintingById(id)).ToArray();
        _metadata=new CardMatcher.CardMatcherMetadata{
            GrpIdsToNumberOwned=printings.ToDictionary(p=>p.GrpId,p=>999),
            TitleIdsToNumberOwned=printings.GroupBy(p=>p.TitleId).ToDictionary(g=>g.Key,g=>999),
            FilteringBySet=false
        };
    }
    public void Set(CardFilterType type,bool enabled)=>_filter.Set(type,enabled);
    public IReadOnlyCollection<CardFilterType> Selected=>_filter.Filters;
    public void Reset(){foreach(var type in Selected.ToArray())_filter.Set(type,false);}
    public List<CardPrintingData> Apply(IEnumerable<uint> ids,string query)
    {
        if(query.Length>256)throw new InvalidDataException("Search is limited to 256 characters.");
        if(!new CardMatcher(query,_database).Successful)throw new InvalidDataException("The Arena search could not be parsed. Check the search terms and try again.");
        _filter.SearchText=query;
        var group=new CardFilterGroup(ids.Select((id,index)=>new CardFilterGroup.FilteredCard(_database.CardDataProvider.GetCardPrintingById(id),index)).ToList());
        foreach(var evaluate in _filter.GetFilterFunctions(_metadata))group=evaluate(group);
        return group.GetFilteredCards_Passed().Select(c=>c.Card).ToList();
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using MovementSystem;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using Wotc.Mtga.DuelScene;
using Wotc.Mtga.DuelScene.Interactions;
using Wotc.Mtga.DuelScene.Browsers;
using Wotc.Mtgo.Gre.External.Messaging;
using Action = System.Action;
using Color = UnityEngine.Color;

namespace ForgeArenaSandbox;

// A shared table for native pod players. The hand, stack, card browsers,
// rules, priority responses and animation scheduler keep their native paths.
// Transform movement goals so input colliders and targeting lines follow cards.
internal sealed class NativeCommanderPodView : MonoBehaviour
{
    internal static NativeCommanderPodView? Active { get; private set; }
    private GameManager _game = null!;
    private PAPA _papa = null!;
    private PlayerFocusController_Quadrant _focus = null!;
    private Transform _camera = null!;
    private GameObject _hud = null!;
    private Action _showDetails = null!;
    private readonly Dictionary<DuelScene_AvatarView, (Vector3 position, Vector3 scale)> _avatars = new Dictionary<DuelScene_AvatarView, (Vector3, Vector3)>();
    private readonly Dictionary<uint, SeatPanel> _seats = new Dictionary<uint, SeatPanel>();
    private readonly Dictionary<uint, LineRenderer> _lanes = new Dictionary<uint, LineRenderer>();
    private readonly Dictionary<uint, float> _battlefieldFit = new Dictionary<uint, float>();
    private readonly Dictionary<CardHolderBase, ZonePose> _zones = new Dictionary<CardHolderBase, ZonePose>();
    private readonly Dictionary<BoxCollider, Vector3> _zoneColliderSizes = new Dictionary<BoxCollider, Vector3>();
    private readonly Dictionary<Transform, Vector3> _effectScales = new Dictionary<Transform, Vector3>();
    private Material? _laneMaterial;
    private TMP_FontAsset _font = null!, _bodyFont = null!;
    private readonly Dictionary<string, Sprite> _sprites = new Dictionary<string, Sprite>();
    private TMP_Text _turn = null!, _priority = null!, _viewLabel = null!;
    private Image _turnAccent = null!;
    private RectTransform _turnPanel = null!, _navPanel = null!, _detailsPanel = null!;
    private int _layoutWidth, _layoutHeight;
    private float _layoutScale;
    private float _nextRefresh;
    private string _lastWorkflow = "";
    private bool _started;
    private uint _focusedSeat;
    private readonly PodSpectatorPolicy _spectator=new PodSpectatorPolicy();
    private readonly Dictionary<uint,Vector3> _offsets=new Dictionary<uint,Vector3>();
    private readonly Dictionary<uint,DuelScene_AvatarView> _avatarBySeat=new Dictionary<uint,DuelScene_AvatarView>();
    private readonly HashSet<CardHolderBase> _holders=new HashSet<CardHolderBase>();
    private uint[] _alive=new uint[0];
    private TMP_Text _navTitle=null!;
    private float _nextNames;
    private bool Rail=>_spectator.Rail;
    internal object Snapshot()=>new{rail=Rail,following=_spectator.Following,watched=_focusedSeat,pinned=_spectator.Pinned,alive=_alive,overview=Overview,registeredSeats=SeatCount,publicBoardsVisible=Rail?(_focusedSeat==1?1:2):_alive.Length};
    private static bool _patched;
    private static readonly FieldInfo HolderGame = AccessTools.Field(typeof(CardHolderBase), "_gameManager");
    private static readonly MethodInfo SetPlayerVisibility = AccessTools.Method(typeof(PlayerFocusController_Quadrant), "SetPlayerVisibility");
    private static readonly Color Gold = new Color(.91f, .66f, .27f, 1), Aqua = new Color(.35f, .84f, .89f, 1);
    private static readonly Color[] SeatColors = { Color.clear, new Color(.78f, .65f, .41f), new Color(.39f, .69f, .88f), new Color(.72f, .52f, .83f), new Color(.39f, .76f, .64f) };
    private PodTableLayout _layout = new PodTableLayout(new uint[0]);
    private object _nativeOffsetCalculator = null!;
    private MethodInfo _getNativeOffset = null!;
    private int SeatCount => NativePodLayoutPatches.RegisteredSeats>0 ? NativePodLayoutPatches.RegisteredSeats : _game.CurrentGameState?.Players.Count ?? 0;
    internal bool HasSeat(uint seat) => seat>=1 && seat<=SeatCount;
    private static Color SeatColor(uint seat)=>SeatColors[1+(seat-1)%4];
    public int CopiedBoardMeshes => 0;
    public bool Overview => _focusedSeat == 0;
    internal BrowserBase? CurrentBrowser => _game?.BrowserManager?.CurrentBrowser;
    internal bool IsReady => _game != null && _game.CurrentGameState != null && SeatCount >= 3 && _game.CurrentGameState.GameInfo?.Stage == GameStage.Play;
    internal bool Owns(CardHolderBase holder) => ReferenceEquals(HolderGame.GetValue(holder), _game);
    internal bool Owns(PlayerFocusController_Quadrant focus) => ReferenceEquals(focus, _focus);
    public static void Ensure(GameManager game, PAPA papa, Action showDetails)
    {
        if (game.GetComponent<NativeCommanderPodView>() != null || game.CurrentGameState==null || game.CurrentGameState.Players.Count < 3) return;
        var view = game.gameObject.AddComponent<NativeCommanderPodView>();
        try { view.Initialize(game, papa, showDetails); } catch { UnityEngine.Object.Destroy(view); throw; }
    }
    private void Initialize(GameManager game, PAPA papa, Action showDetails)
    {
        _game = game; _papa = papa; _showDetails = showDetails;
        _focus = game.Context.Get<IPlayerFocusController>() as PlayerFocusController_Quadrant ?? throw new NotSupportedException("Native pod camera is unavailable");
        _camera = (Transform)AccessTools.Field(typeof(PlayerFocusController_Quadrant), "_cameraTransform").GetValue(_focus);
        if (!_patched) { NativePodLayoutPatches.Install(); _patched = true; }
        var offsetField=AccessTools.Field(typeof(PlayerFocusController_Quadrant), "_playerOffsetCalculator");
        _nativeOffsetCalculator=offsetField.GetValue(_focus);_getNativeOffset=offsetField.FieldType.GetMethod("GetOffset")!;
        _layout=new PodTableLayout(_game.CurrentGameState.Players.Where(p=>p.Status==PlayerStatus.InGame).Select(p=>p.InstanceId).ToArray());
        _alive=_layout.Alive;
        _spectator.Update(_alive,_game.CurrentGameState.ActivePlayer?.InstanceId??0);
        _focusedSeat=Rail?_spectator.Watched:0;
        Active = this; BuildControls(); BuildLanes();
        foreach(var holder in UnityEngine.Object.FindObjectsByType<CardHolderBase>(FindObjectsSortMode.None))if(Owns(holder))_holders.Add(holder);
    }
    internal Vector3 NativeOffset(uint seat)
    {
        if(!_offsets.TryGetValue(seat,out var value)){value=(Vector3)_getNativeOffset.Invoke(_nativeOffsetCalculator,new object[]{seat});_offsets[seat]=value;}
        return value;
    }
    internal float Scale(uint seat, bool battlefield = false) => !Overview ? 1f : battlefield && _battlefieldFit.TryGetValue(seat, out var fit) ? fit : seat == 1 ? _layout.LocalScale : _layout.OpponentScale;
    internal void FitBattlefields(List<CardLayoutData> layout)
    {
        // Fit actual generated card extents inside each ownership lane. A full
        // opponent board must never spill into its neighbor's battlefield.
        // This affects presentation only; focus and native hover remain large.
        _battlefieldFit.Clear();
        foreach (var group in layout.Where(d => d.IsVisibleInLayout && d.Card?.Model?.Instance?.Controller != null).GroupBy(d => d.Card.Model.Instance.Controller.InstanceId))
        {
            uint seat = group.Key; if (!HasSeat(seat)) continue;
            float extent = 0;
            foreach (var data in group)
            {
                // A collider's diagonal also bounds a tapped or turning card;
                // its local x width alone can under-fit a crowded lane.
                float radius = Vector3.Scale(data.Card.Collider.size, data.Scale).magnitude * .5f;
                extent = Mathf.Max(extent, Mathf.Abs(data.Position.x - NativeOffset(seat).x) + radius);
            }
            float normal = seat == 1 ? _layout.LocalScale : _layout.OpponentScale, available = seat == 1 ? 27.5f : _layout.HalfWidth;
            _battlefieldFit[seat] = extent > .01f ? Mathf.Min(normal, available / extent) : normal;
        }
    }
    internal Vector3 MapPoint(Vector3 source, uint seat, bool battlefield = false)
    {
        var p = source - NativeOffset(seat);
        if (!Overview)
        {
            // A focused view retains you and one opponent. Other players keep
            // their status panels and stable seat IDs, with cards off camera.
            if (seat != 1 && seat != _focusedSeat) p.x += 200 + seat * 60;
            return p;
        }
        float scale = Scale(seat, battlefield); p.x *= scale; p.z *= scale;
        p.x += _layout.X(seat); p.z += _layout.Z(seat);
        return p;
    }
    internal void MapEndpoint(CardHolderBase holder, CardLayoutData data, ref IdealPoint endpoint)
    {
        if (!IsReady || !Owns(holder) || data.Card?.Model?.Instance == null) return;
        string kind = holder.CardHolderType.ToString(); var instance = data.Card.Model.Instance;
        uint seat = kind == "Battlefield" ? instance.Controller?.InstanceId ?? 0 : instance.Zone?.OwnerId ?? 0;
        if (seat == 0) seat = instance.Owner?.InstanceId ?? 0;
        if (!HasSeat(seat)) return;
        // Camera-relative local hand/command and modal browsers stay native.
        // Mapping never reveals a hidden card or changes a legal target ID.
        bool map = kind == "Battlefield" || kind == "Library" || kind == "Graveyard" || kind == "Exile" || kind == "Hand" && seat != 1 || kind == "Command" && seat != 1;
        if (!map) return; bool battlefield = kind == "Battlefield";
        // A zone's real input surface and effect origin move with its holder.
        // Recover the native point before applying the single table transform.
        if (_zones.TryGetValue(holder, out var zone)) endpoint.Position -= zone.Delta;
        endpoint.Position = MapPoint(endpoint.Position, seat, battlefield); endpoint.Scale *= Scale(seat, battlefield);
    }
    internal string PlayerLabel(uint seat) => seat == 1 ? "You" : _papa.MatchManager.Players.SingleOrDefault(p => p.SeatId == seat)?.ScreenName ?? "Player " + seat;
    internal void PositionZone(CardHolderBase holder, uint seat, bool nativeReset = false)
    {
        if (!IsReady || !Owns(holder) || !HasSeat(seat)) return;
        _holders.Add(holder);
        string kind = holder.CardHolderType.ToString(); if (kind != "Library" && kind != "Graveyard" && holder is not PlayerExileCardHolder) return;
        if (!_zones.TryGetValue(holder, out var pose) || nativeReset) { pose = new ZonePose { Seat = seat, Source = holder.transform.position }; _zones[holder] = pose; }
        holder.transform.position = MapPoint(pose.Source, pose.Seat); pose.Delta = holder.transform.position - pose.Source;
        foreach (var box in holder.GetComponentsInChildren<BoxCollider>(true).Where(c => c.GetComponentInParent<DuelScene_CDC>() == null))
        {
            if (!_zoneColliderSizes.TryGetValue(box, out var size)) { size = box.size; _zoneColliderSizes[box] = size; }
            box.size = size * Scale(pose.Seat);
        }
    }
    private void PositionZones()
    {
        foreach(var entry in _zones.ToArray())if(entry.Key!=null)PositionZone(entry.Key,entry.Value.Seat);
        foreach(var holder in _holders.OfType<ZoneCardHolderBase>().ToArray())
        {
            if(holder==null)continue;
            uint seat=holder.GetZone?.OwnerId??0;
            if(holder is PlayerExileCardHolder)seat=(uint)AccessTools.Field(typeof(PlayerExileCardHolder),"_playerId").GetValue(holder);
            if(!_zones.ContainsKey(holder))PositionZone(holder,seat);
        }
    }
    internal void LibraryCollider(LibraryCardHolder holder)
    {
        if (!IsReady || !_zones.TryGetValue(holder, out var pose) || holder.TopCard?.Collider == null) return;
        var box = (BoxCollider)AccessTools.Field(typeof(LibraryCardHolder), "_inputCollider").GetValue(holder);
        box.size = holder.TopCard.Collider.size * holder.CardScale * Scale(pose.Seat);
    }
    internal void GraveyardEffect(GraveyardCardHolder holder)
    {
        if (!IsReady || !_zones.TryGetValue(holder, out var pose)) return;
        var effect = (Transform)AccessTools.Field(typeof(GraveyardCardHolder), "_effectRoot").GetValue(holder);
        if (effect == null || AccessTools.Field(typeof(GraveyardCardHolder), "_effectSystem").GetValue(holder) == null) return;
        if (!_effectScales.TryGetValue(effect, out var scale)) { scale = effect.localScale; _effectScales[effect] = scale; }
        effect.position = MapPoint(effect.position - pose.Delta, pose.Seat); effect.localScale = scale * Scale(pose.Seat);
    }
    internal void LabelZoneBrowser(ZoneCardHolderBase holder)
    {
        if (!IsReady || !Owns(holder) || _game.BrowserManager.CurrentBrowser is not CardBrowserBase browser) return;
        uint seat = _zones.TryGetValue(holder, out var pose) ? pose.Seat : holder.GetZone?.OwnerId ?? 0; if (!HasSeat(seat)) return;
        var elements = (Dictionary<string, DuelSceneBrowserElementData>)AccessTools.Field(typeof(BrowserBase), "uiElementData").GetValue(browser);
        string zone = holder.CardHolderType.ToString().ToLowerInvariant();
        foreach (var header in elements.Values.Where(e => e.GameObject != null).SelectMany(e => e.GameObject.GetComponentsInChildren<BrowserHeader>(true)).Distinct())
            header.SetHeaderText((seat == 1 ? "Your" : PlayerLabel(seat) + "'s") + " " + zone);
    }
    public void ShowTable()
    {
        if(Rail){_spectator.Follow();_spectator.Update(_alive,_game.CurrentGameState.ActivePlayer?.InstanceId??0);SetView(_spectator.Watched);}
        else SetView(0);
    }
    public void ShowSeat(uint seat)
    {
        if(!_game.Context.Get<IDuelSceneStateProvider>().CurrentState.Value.AllowInput || _game.CurrentGameState?.GetPlayerById(seat)?.Status!=PlayerStatus.InGame)return;
        if(Rail){_spectator.Inspect(seat);SetView(seat);return;}
        if(SelectingAcrossPlayers)return;
        SetView(_focusedSeat==seat?0:seat);
    }
    private void SetView(uint seat)
    {
        _focusedSeat = seat; var field = AccessTools.Field(typeof(PlayerFocusController_Quadrant), "_focusMode"); field.SetValue(_focus, Enum.Parse(field.FieldType, "All"));
        _game.SplineMovementSystem.AddPermanentGoal(_camera, new IdealPoint(_camera) { Position = CameraPosition(Overview) });
        PositionAvatars(); PositionZones(); AlignHeaders(); foreach(var card in _game.ViewManager.GetAllCards())if(card!=null && card.CurrentCardHolder is CardHolderBase holder)_holders.Add(holder);
        foreach(var holder in _holders.ToArray())if(holder!=null)holder.LayoutNow(); Refresh();
    }
    private Vector3 CameraPosition(bool table)
    {
        float aspect = Screen.width / (float)Mathf.Max(1, Screen.height), fit = Mathf.Max(1, (16f / 9) / aspect);
        return (table ? new Vector3(0, _layout.CameraHeight, _layout.CameraDepth) : new Vector3(0, 50.5f, 19)) * fit;
    }
    private void AlignHeaders()
    {
        var camera=Camera.main;if(camera==null || _seats.Count<3)return;
        _layoutWidth=Screen.width;_layoutHeight=Screen.height;
        float scale=_hud.GetComponent<Canvas>().scaleFactor;if(scale<=0)return;_layoutScale=scale;
        if(Rail){AlignRail();return;}
        Place(_navPanel,new Vector2(0,1),new Vector2(18,-18),new Vector2(174,62));
        Place(_turnPanel,new Vector2(0,1),new Vector2(18,-88),new Vector2(174,112));
        Place(_detailsPanel,new Vector2(0,1),new Vector2(18,-208),new Vector2(174,38));
        _detailsPanel.gameObject.SetActive(true);_navTitle.text="Table view";
        HeaderText(174,112);
        Place(_seats[1].Root,Vector2.zero,new Vector2(24,126),new Vector2(360,88));
        ArrangeSeat(_seats[1],360);
        var delta=CameraPosition(true)-_camera.position;var centers=new Dictionary<uint,float>();var visible=_layout.Opponents;
        foreach(var entry in _seats.Where(e=>e.Key!=1))entry.Value.Root.gameObject.SetActive(_layout.Has(entry.Key));
        float width=visible.Length<=1?390:visible.Length==2?360:Mathf.Min(390,Mathf.Max(270,(Screen.width/3f-36)/scale));
        foreach(uint seat in visible)
        {
            var original=_avatars.FirstOrDefault(p=>p.Key!=null && p.Key.InstanceId==seat);
            var point=original.Key!=null?original.Value.position:NativeOffset(seat)+new Vector3(0,3.69f,-11.33f);
            centers[seat]=camera.WorldToScreenPoint(MapPoint(point,seat)-delta).x;
        }
        foreach(var row in visible.GroupBy(seat=>_layout.Slot(seat)/3))
        {
            var x=row.Select(seat=>centers[seat]).OrderBy(v=>v).ToArray();
            for(int i=1;i<x.Length;i++)width=Mathf.Min(width,Mathf.Max(232,(x[i]-x[i-1]-12)/scale));
        }
        foreach(uint seat in visible)
        {
            var ui=_seats[seat];int row=Math.Max(0,_layout.Slot(seat)/3);
            ui.Root.anchorMin=ui.Root.anchorMax=new Vector2(centers[seat]/Screen.width,1);ui.Root.pivot=new Vector2(.5f,1);
            ui.Root.anchoredPosition=new Vector2(0,-14-row*94);ui.Root.sizeDelta=new Vector2(width,88);ArrangeSeat(ui,width);
        }
    }
    private void AlignRail()
    {
        const float width=336;
        Place(_navPanel,new Vector2(0,1),new Vector2(14,-14),new Vector2(width,60));_navTitle.text="Follow turn";
        Place(_turnPanel,new Vector2(0,1),new Vector2(14,-80),new Vector2(width,86));HeaderText(width,86);
        _detailsPanel.gameObject.SetActive(true);
        int index=0;
        foreach(var entry in _seats.OrderBy(e=>e.Key))
        {
            var ui=entry.Value;bool living=_layout.Has(entry.Key);ui.Root.gameObject.SetActive(living);if(!living)continue;
            Place(ui.Root,new Vector2(0,1),new Vector2(14,-178-index++*80),new Vector2(width,78));ArrangeSeat(ui,width);
        }
        Place(_detailsPanel,new Vector2(0,1),new Vector2(14,-184-index*80),new Vector2(width,34));
    }
    private static void Place(RectTransform rect,Vector2 anchor,Vector2 position,Vector2 size)
    {rect.anchorMin=rect.anchorMax=rect.pivot=anchor;rect.anchoredPosition=position;rect.sizeDelta=size;}
    private void HeaderText(float width,float height)
    {
        _navTitle.rectTransform.sizeDelta=new Vector2(width-24,29);
        _viewLabel.rectTransform.sizeDelta=new Vector2(width-24,22);
        _turn.rectTransform.sizeDelta=new Vector2(width-24,height-27);_turn.fontSize=22;
        _priority.rectTransform.sizeDelta=new Vector2(width-24,22);
        _turnAccent.rectTransform.sizeDelta=new Vector2(width-16,2);
        _detailsPanel.GetComponentInChildren<TMP_Text>().rectTransform.sizeDelta=new Vector2(width-20,28);
    }
    private static void ArrangeSeat(SeatPanel ui,float width)
    {
        ui.Title.rectTransform.sizeDelta=new Vector2(width-96,29);
        ui.Status.rectTransform.sizeDelta=new Vector2(width-96,22);
        ui.Target.root.anchoredPosition=new Vector2(width-82,-29);ui.Target.root.sizeDelta=new Vector2(76,24);ui.Target.label.rectTransform.sizeDelta=new Vector2(70,24);
        float cell=(width-96)/4;
        Place(ui.Hand,new Vector2(0,1),new Vector2(88,-53),new Vector2(cell,23));
        Place(ui.Library,new Vector2(0,1),new Vector2(88+cell,-53),new Vector2(cell,23));
        Place(ui.Graveyard.root,new Vector2(0,1),new Vector2(88+cell*2,-53),new Vector2(cell,23));
        Place(ui.Exile.root,new Vector2(0,1),new Vector2(88+cell*3,-53),new Vector2(cell,23));
        foreach(var root in new[]{ui.Hand,ui.Library,ui.Graveyard.root,ui.Exile.root})
        {
            var label=root.GetComponentInChildren<TMP_Text>();label.rectTransform.sizeDelta=new Vector2(Mathf.Max(18,cell-23),23);
        }
    }
    private void PositionAvatars()
    {
        foreach (var avatar in _game.ViewManager.GetAllAvatars())
        {
            _avatarBySeat[avatar.InstanceId]=avatar;
            if (!_avatars.TryGetValue(avatar, out var original)) { original = (avatar.transform.position, avatar.transform.localScale); _avatars[avatar] = original; }
            var p = MapPoint(original.position, avatar.InstanceId);
            var scale=original.scale * (Overview ? (avatar.InstanceId == 1 ? _layout.LocalScale : _layout.OpponentScale*1.23f) : 1f);
            if(avatar.transform.position!=p)avatar.transform.position=p;
            if(avatar.transform.localScale!=scale)avatar.transform.localScale=scale;
        }
    }
    private void BuildControls()
    {
        var fonts=Resources.FindObjectsOfTypeAll<TMP_FontAsset>();
        _font=fonts.FirstOrDefault(f=>f.name=="Font_Title")??throw new NotSupportedException("The installed Arena title font is unavailable");
        _bodyFont=fonts.FirstOrDefault(f=>f.name=="Font_Default")??throw new NotSupportedException("The installed Arena body font is unavailable");
        foreach(var sprite in Resources.FindObjectsOfTypeAll<Sprite>())if(!_sprites.ContainsKey(sprite.name))_sprites[sprite.name]=sprite;
        _hud=new GameObject("Commander pod shared table",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));_hud.transform.SetParent(_game.transform,false);
        var canvas=_hud.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=31000;
        var scaler=_hud.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1920,1080);scaler.matchWidthOrHeight=.5f;
        for(uint seat=1;seat<=SeatCount;seat++)BuildSeat(seat);
        _turnPanel=Panel("Turn and priority",_hud.transform,new Vector2(0,1),Vector2.zero,new Vector2(336,86),new Color(.015f,.018f,.022f,.78f));
        _turnAccent=Art("Turn accent",_turnPanel,"GradientFadeBacker",new Vector2(.5f,0),new Vector2(0,0),new Vector2(300,2),Gold);
        _turn=Text("Turn",_turnPanel,new Vector2(.5f,1),new Vector2(0,-4),new Vector2(312,60),22,TextAlignmentOptions.Center);_turn.font=_font;Fit(_turn,16,22);
        _priority=Text("Priority",_turnPanel,new Vector2(.5f,0),new Vector2(0,5),new Vector2(312,22),17,TextAlignmentOptions.Center);_priority.color=new Color(.77f,.80f,.82f);Fit(_priority,14,17);
        _navPanel=Panel("Table navigation",_hud.transform,new Vector2(0,1),Vector2.zero,new Vector2(336,60),Color.white);
        Skin(_navPanel.GetComponent<Image>(),"MainButton_OutlineDarkFill",Color.white);ClickArea(_navPanel,ShowTable);
        _navTitle=Text("Follow turn",_navPanel,new Vector2(.5f,1),new Vector2(0,-3),new Vector2(312,29),23,TextAlignmentOptions.Center);_navTitle.font=_font;
        _viewLabel=Text("View",_navPanel,new Vector2(.5f,0),new Vector2(0,5),new Vector2(312,22),16,TextAlignmentOptions.Center);Fit(_viewLabel,12,16);_viewLabel.color=new Color(.75f,.74f,.69f);
        _detailsPanel=Panel("Pod details",_hud.transform,new Vector2(0,1),Vector2.zero,new Vector2(336,34),Color.white);Skin(_detailsPanel.GetComponent<Image>(),"MainButton_OutlineDarkFill",new Color(.88f,.85f,.77f,.9f));ClickArea(_detailsPanel,_showDetails);
        var details=Text("Commander damage  [F5]",_detailsPanel,new Vector2(.5f,.5f),Vector2.zero,new Vector2(316,28),16,TextAlignmentOptions.Center);Fit(details,12,16);
        _hud.SetActive(false);
    }
    private void BuildSeat(uint seat)
    {
        var panel=Panel("Commander pod seat "+seat,_hud.transform,new Vector2(0,1),Vector2.zero,new Vector2(336,78),new Color(.015f,.018f,.024f,.82f));
        uint selected=seat;var button=ClickArea(panel,()=>ClickSeat(selected));
        var accent=Art("Arena selection edge",panel,"BannerFrame_Rounded",new Vector2(.5f,.5f),Vector2.zero,new Vector2(336,78),new Color(.72f,.60f,.38f,.35f));
        Stretch(accent.rectTransform);button.targetGraphic=accent;
        Art("Native avatar frame",panel,"ProfileFrame",new Vector2(0,1),new Vector2(5,-4),new Vector2(76,61),Color.white);
        var mask=Art("Native portrait mask",panel,"secondaryOutlineButtonFill",new Vector2(0,1),new Vector2(19,-7),new Vector2(48,44),Color.white);
        mask.gameObject.AddComponent<Mask>().showMaskGraphic=false;
        var player=_papa.MatchManager.Players.Single(p=>p.SeatId==seat);
        string portraitPath=ProfileUtilities.GetAvatarBustImagePath(_papa.AssetLookupSystem,player.AvatarSelection);
        string portraitName=System.IO.Path.GetFileNameWithoutExtension(portraitPath);
        var portrait=Art("Native player portrait",mask.transform,portraitName,new Vector2(.5f,.5f),Vector2.zero,new Vector2(48,44),Color.white);
        // Atlas trimming leaves transparent padding in the sprite's logical
        // rect. Fit its actual visible content, without copying or editing art.
        var sprite=portrait.sprite;var crop=sprite.textureRect;var offset=sprite.textureRectOffset;
        float zoom=Mathf.Min(48/crop.width,44/crop.height);
        portrait.rectTransform.sizeDelta=sprite.rect.size*zoom;
        portrait.rectTransform.anchoredPosition=-(offset+crop.size*.5f-sprite.rect.size*.5f)*zoom;
        var lifeBacker=Art("Native life medallion",panel,"ZoneCount_Backer",new Vector2(0,1),new Vector2(22,-49),new Vector2(42,28),new Color(.065f,.063f,.054f,1));
        var life=Text("Life",panel,new Vector2(0,1),new Vector2(22,-48),new Vector2(42,30),26,TextAlignmentOptions.Center);life.font=_font;Fit(life,10,26);
        var title=Text("Name",panel,new Vector2(0,1),new Vector2(88,-3),new Vector2(240,29),23,TextAlignmentOptions.MidlineLeft);title.font=_font;Fit(title,18,23);
        var status=Text("Status",panel,new Vector2(0,1),new Vector2(88,-30),new Vector2(240,22),16,TextAlignmentOptions.MidlineLeft);Fit(status,13,16);
        var hand=ZoneReadout(panel,"Hand","icon_count_hand");var library=ZoneReadout(panel,"Library","icon_count_library");
        var graveyard=ZoneButton(panel,"Graveyard","icon_count_graveyard",()=>OpenPublicZone(selected,ZoneType.Graveyard));
        var exile=ZoneButton(panel,"Exile","icon_count_exile",()=>OpenPublicZone(selected,ZoneType.Exile));
        var target=ZoneButton(panel,"Target",null,()=>SelectPlayer(selected));target.root.gameObject.SetActive(false);Skin(target.root.GetComponent<Image>(),"MainButton_OutlineDarkFill",new Color(.5f,.8f,.9f,1));
        _seats[seat]=new SeatPanel{Root=panel,Button=button,Background=panel.GetComponent<Image>(),Accent=accent,Portrait=portrait,Title=title,Life=life,Counts=hand.label,LibraryCount=library.label,Hand=hand.root,Library=library.root,Status=status,Graveyard=graveyard,Exile=exile,Target=target};
        ArrangeSeat(_seats[seat],336);
    }
    private (RectTransform root,TMP_Text label) ZoneReadout(Transform parent,string name,string? sprite)
    {
        var root=Panel(name+" public zone",parent,new Vector2(0,1),Vector2.zero,new Vector2(58,23),Color.clear);
        if(sprite!=null){var icon=Art("Arena "+name+" icon",root,sprite,new Vector2(0,.5f),Vector2.zero,new Vector2(19,19),new Color(.78f,.77f,.71f));icon.preserveAspect=true;}
        var label=Text(name+" count",root,new Vector2(0,.5f),new Vector2(sprite==null?3:23,0),new Vector2(32,23),18,TextAlignmentOptions.MidlineLeft);Fit(label,14,18);
        return(root,label);
    }
    private (RectTransform root,Button button,TMP_Text label) ZoneButton(Transform parent,string name,string? sprite,Action action)
    {
        var view=ZoneReadout(parent,name,sprite);var button=ClickArea(view.root,action);button.targetGraphic=view.label;button.transition=Selectable.Transition.ColorTint;
        var colors=button.colors;colors.normalColor=new Color(.91f,.89f,.83f);colors.highlightedColor=Gold;colors.selectedColor=colors.normalColor;colors.pressedColor=Aqua;colors.disabledColor=new Color(.54f,.55f,.54f);button.colors=colors;
        return(view.root,button,view.label);
    }
    private static void Fit(TMP_Text text,float min,float max)
    {text.enableAutoSizing=true;text.fontSizeMin=min;text.fontSizeMax=max;text.overflowMode=TextOverflowModes.Ellipsis;}
    private static void Stretch(RectTransform rect)
    {rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=rect.offsetMax=Vector2.zero;}
    private void Skin(Image image,string sprite,Color color)
    {
        if(!_sprites.TryGetValue(sprite,out var value))throw new NotSupportedException("The installed Arena artwork is unavailable: "+sprite);
        image.sprite=value;image.type=value.border.sqrMagnitude>0?Image.Type.Sliced:Image.Type.Simple;image.color=color;
    }
    private Image Art(string name,Transform parent,string sprite,Vector2 anchor,Vector2 position,Vector2 size,Color color)
    {
        var obj=new GameObject(name,typeof(RectTransform),typeof(Image));var rect=(RectTransform)obj.transform;rect.SetParent(parent,false);Place(rect,anchor,position,size);
        var image=obj.GetComponent<Image>();Skin(image,sprite,color);image.raycastTarget=false;return image;
    }
    private void OpenPublicZone(uint seat, ZoneType zone)
    {
        if (!IsReady || _game.BrowserManager.IsBrowserVisible || _game.CurrentGameState.GetPlayerById(seat)?.Status != PlayerStatus.InGame) return;
        var holder = _zones.FirstOrDefault(p => p.Value.Seat == seat && (zone == ZoneType.Graveyard ? p.Key is GraveyardCardHolder : p.Key is PlayerExileCardHolder)).Key;
        if (holder == null) throw new InvalidOperationException("The native " + zone + " holder for seat " + seat + " is unavailable");
        // Delegate browsing and any legal card selection to the owned native
        // holder. The panel never constructs a substitute list of cards.
        if (holder is GraveyardCardHolder graveyard) graveyard.ViewGraveyard(_game.InteractionSystem.HandleViewDismissCardClick);
        else ((IPointerClickHandler)holder).OnPointerClick(new PointerEventData(EventSystem.current));
    }
    private RectTransform Panel(string name, Transform parent, Vector2 anchor, Vector2 position, Vector2 size, Color color)
    {
        var obj = new GameObject(name, typeof(RectTransform), typeof(Image)); var r = (RectTransform)obj.transform; r.SetParent(parent, false); r.anchorMin = r.anchorMax = anchor; r.pivot = anchor; r.anchoredPosition = position; r.sizeDelta = size; var image = obj.GetComponent<Image>(); image.color = color; image.raycastTarget = false;
        if(size.x>=150 && size.y>=34)Skin(image,"GradientBackerR",color);
        return r;
    }
    private TMP_Text Text(string name, Transform parent, Vector2 anchor, Vector2 position, Vector2 size, float fontSize, TextAlignmentOptions alignment)
    {
        var obj = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI)); var r = (RectTransform)obj.transform; r.SetParent(parent, false); r.anchorMin = r.anchorMax = anchor; r.pivot = anchor; r.anchoredPosition = position; r.sizeDelta = new Vector2(size.x, Mathf.Max(size.y, fontSize * 1.3f));
        var text = obj.GetComponent<TextMeshProUGUI>(); text.font = _bodyFont; text.fontSize = fontSize; text.text = name; text.color = new Color(.92f, .91f, .87f); text.alignment = alignment; text.raycastTarget = false; text.textWrappingMode = TextWrappingModes.NoWrap; text.overflowMode = TextOverflowModes.Overflow; return text;
    }
    private static Button ClickArea(RectTransform panel, Action action)
    {
        panel.GetComponent<Image>().raycastTarget = true; var button = panel.gameObject.AddComponent<Button>(); button.targetGraphic = panel.GetComponent<Image>(); button.transition = Selectable.Transition.ColorTint; var colors=button.colors;colors.normalColor=Color.white;colors.highlightedColor=new Color(1,.84f,.56f);colors.pressedColor=Aqua;colors.selectedColor=Color.white;button.colors=colors; button.onClick.AddListener(() => action()); return button;
    }
    private void BuildLanes()
    {
        var shader = Shader.Find("Sprites/Default"); if (shader == null) return;
        _laneMaterial = new Material(shader);
        for (uint seat = 1; seat <= SeatCount; seat++)
        {
            var obj = new GameObject("Commander pod lane " + seat); obj.transform.SetParent(_game.transform, false);
            var line = obj.AddComponent<LineRenderer>(); line.sharedMaterial = _laneMaterial; line.useWorldSpace = true; line.loop = true; line.positionCount = 4; line.startWidth = line.endWidth = .075f;
            float center=_layout.X(seat);float half=seat==1?28:_layout.HalfWidth+.4f,near=seat==1?21:_layout.Z(seat)+2,far=seat==1?3:_layout.Z(seat)-17*_layout.OpponentScale*1.2f;
            line.SetPositions(new[] { new Vector3(center - half, .65f, far), new Vector3(center + half, .65f, far), new Vector3(center + half, .65f, near), new Vector3(center - half, .65f, near) }); _lanes[seat] = line;
        }
    }
    private bool CanSelectPlayer(uint seat)
    {
        var workflow = _game.WorkflowController.CurrentWorkflow as IClickableWorkflow;
        _avatarBySeat.TryGetValue(seat,out var avatar);
        return workflow != null && _game.WorkflowController.CurrentWorkflow.AppliedState == InteractionAppliedState.Applied && avatar != null && workflow.CanClick(avatar, SimpleInteractionType.Primary);
    }
    private bool SelectingAcrossPlayers
    {
        get { string name = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? ""; return name.IndexOf("Target", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("Attack", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("Block", StringComparison.OrdinalIgnoreCase) >= 0 || _game.CurrentGameState.Players.Any(p => CanSelectPlayer(p.InstanceId)); }
    }
    private void SelectPlayer(uint seat)
    {
        if(!CanSelectPlayer(seat))return;
        var avatar=_game.ViewManager.GetAllAvatars().Single(v=>v.InstanceId==seat);
        ((IClickableWorkflow)_game.WorkflowController.CurrentWorkflow).OnClick(avatar,SimpleInteractionType.Primary);
    }
    private void ClickSeat(uint seat)
    {
        if(Rail){ShowSeat(seat);return;}
        if (CanSelectPlayer(seat))
        {
            var avatar = _game.ViewManager.GetAllAvatars().Single(v => v.InstanceId == seat);
            ((IClickableWorkflow)_game.WorkflowController.CurrentWorkflow).OnClick(avatar, SimpleInteractionType.Primary); return;
        }
        // An ineligible player panel cannot accidentally hide other targets.
        if (_game.CurrentGameState.Players.Any(p => CanSelectPlayer(p.InstanceId))) return;
        ShowSeat(seat);
    }
    private void Update()
    {
        if (_game == null || _hud == null || _game.CurrentGameState==null) return;
        var state=_game.CurrentGameState;
        if(Time.unscaledTime>=_nextRefresh)
        {
            var alive=state.Players.Where(p=>p.Status==PlayerStatus.InGame).Select(p=>p.InstanceId).OrderBy(v=>v).ToArray();
            bool layoutChanged=!_alive.SequenceEqual(alive);_alive=alive;
            if(layoutChanged)
            {
                _layout=new PodTableLayout(alive);_battlefieldFit.Clear();
                foreach(var lane in _lanes.Values)UnityEngine.Object.Destroy(lane.gameObject);_lanes.Clear();if(_laneMaterial!=null)UnityEngine.Object.Destroy(_laneMaterial);BuildLanes();
            }
            string flow=_game.WorkflowController.CurrentWorkflow?.GetType().Name??"";
            uint defenderView=0;
            if(flow.IndexOf("Block",StringComparison.OrdinalIgnoreCase)>=0)
                defenderView=state.Battlefield.VisibleCards.FirstOrDefault(c=>c.AttackTargetId==1 && c.AttackState!=AttackState.None)?.Controller?.InstanceId??0;
            bool changed=_spectator.Update(alive,state.ActivePlayer?.InstanceId??0,defenderView);
            if(changed||layoutChanged)SetView(Rail?_spectator.Watched:0);
        }
        bool play = IsReady && !_game.BrowserManager.IsBrowserVisible && !_game.Context.Get<SettingsMenuHost>().IsOpen(); _hud.SetActive(play); if (!play) { foreach (var lane in _lanes.Values) lane.enabled = false; return; }
        if (!_started) { _started = true; SetView(Rail?_spectator.Watched:0); }
        if (!Overview && state.GetPlayerById(_focusedSeat)?.Status != PlayerStatus.InGame) ShowTable();
        if (Screen.width != _layoutWidth || Screen.height != _layoutHeight || Mathf.Abs(_hud.GetComponent<Canvas>().scaleFactor - _layoutScale) > .001f) SetView(_focusedSeat);
        var keyboard = Keyboard.current;
        if (keyboard != null && Application.isFocused)
        {
            if (keyboard.tabKey.wasPressedThisFrame) ShowTable(); else if (keyboard.f1Key.wasPressedThisFrame) ShowSeat(1); else if (keyboard.f2Key.wasPressedThisFrame) ShowSeat(2); else if (keyboard.f3Key.wasPressedThisFrame) ShowSeat(3); else if (keyboard.f4Key.wasPressedThisFrame) ShowSeat(4); else if (keyboard.f5Key.wasPressedThisFrame) _showDetails();
        }
        string workflow = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? "";
        if (!Rail && workflow != _lastWorkflow) { _lastWorkflow = workflow; if (!Overview && (workflow.IndexOf("Target", StringComparison.OrdinalIgnoreCase) >= 0 || workflow.IndexOf("Attack", StringComparison.OrdinalIgnoreCase) >= 0 || workflow.IndexOf("Block", StringComparison.OrdinalIgnoreCase) >= 0)) ShowTable(); }
        if (!Rail && !Overview && SelectingAcrossPlayers) ShowTable();
        if (Time.unscaledTime >= _nextRefresh) { _nextRefresh = Time.unscaledTime + .15f; Refresh(); }
    }
    private void LateUpdate()
    {
        if (!IsReady) return; PositionAvatars();
        // The original quadrant names otherwise float down the left edge.
        if(Time.unscaledTime>=_nextNames){_nextNames=Time.unscaledTime+.25f;foreach(uint seat in _seats.Keys)SetPlayerVisibility.Invoke(_focus,new object[]{seat,false});}
    }
    private void Refresh()
    {
        if (_turn == null) return; var state = _game.CurrentGameState; if (state == null) return; uint active = state.ActivePlayer?.InstanceId ?? 0, priority = state.DecidingPlayer?.InstanceId ?? 0;
        string workflowName = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? "";
        bool inputAllowed=_game.Context.Get<IDuelSceneStateProvider>().CurrentState.Value.AllowInput;
        _navPanel.GetComponent<Button>().interactable=inputAllowed;_detailsPanel.GetComponent<Button>().interactable=inputAllowed;
        bool selectingAcross=SelectingAcrossPlayers;
        bool declaringAttacks = workflowName.IndexOf("DeclareAttack", StringComparison.OrdinalIgnoreCase) >= 0;
        var attacks = state.Battlefield.VisibleCards.Where(c => c.Controller != null && c.Zone?.Type == ZoneType.Battlefield && state.Battlefield.CardIds.Contains(c.InstanceId) && c.AttackState != AttackState.None && c.AttackTargetId != 0).ToArray();
        string Name(uint seat) => PlayerLabel(seat);
        foreach (var entry in _seats)
        {
            uint seat = entry.Key; var ui = entry.Value; var player = state.GetPlayerById(seat); bool alive = player?.Status == PlayerStatus.InGame;
            ui.Title.text = Name(seat); ui.Life.text = alive ? player!.LifeTotal.ToString() : "OUT";
            int Count(ZoneType zone) => zone == ZoneType.Exile ? state.Exile.VisibleCards.Count(c => c.Owner?.InstanceId == seat) : (int)(state.GetZoneForPlayer(seat, zone)?.TotalCardCount ?? 0);
            ui.Counts.text=Count(ZoneType.Hand).ToString();ui.LibraryCount.text=Count(ZoneType.Library).ToString();
            int graveyard=Count(ZoneType.Graveyard),exile=Count(ZoneType.Exile);
            ui.Graveyard.root.gameObject.SetActive(alive);ui.Exile.root.gameObject.SetActive(alive);
            ui.Graveyard.label.text=graveyard.ToString();ui.Exile.label.text=exile.ToString();
            ui.Graveyard.button.interactable=inputAllowed && alive && graveyard>0;ui.Exile.button.interactable=inputAllowed && alive && exile>0;
            // Disabled zone buttons still absorb clicks instead of selecting the parent seat.
            ui.Graveyard.root.GetComponent<Image>().raycastTarget=true;ui.Exile.root.GetComponent<Image>().raycastTarget=true;
            bool selectable = alive && CanSelectPlayer(seat);
            ui.Button.interactable=inputAllowed && alive && (Rail || !selectingAcross || selectable);
            ui.Target.root.gameObject.SetActive(Rail && selectable);ui.Target.button.interactable=inputAllowed && selectable;ui.Target.label.text=declaringAttacks?"Attack":"Target";
            ui.Status.rectTransform.sizeDelta=new Vector2(ui.Root.sizeDelta.x-96-(Rail && selectable?82:0),22);
            ui.Status.text=!alive?"Eliminated":selectable?(declaringAttacks?"Choose defender":"Legal target"):seat==active?"Taking a turn":seat==priority?"Has priority":_focusedSeat==seat?"Watching":"";
            var incoming = attacks.Where(c => c.AttackTargetId == seat).ToArray(); var outgoing = attacks.Where(c => c.Controller.InstanceId == seat).ToArray();
            if (alive && !selectable && incoming.Length > 0) ui.Status.text = incoming.Length + " attacker" + (incoming.Length == 1 ? "" : "s") + " from " + string.Join(", ", incoming.Select(c => PlayerLabel(c.Controller.InstanceId)).Distinct());
            else if (alive && !selectable && outgoing.Length > 0)
            {
                var targets = outgoing.Select(c => HasSeat(c.AttackTargetId) ? PlayerLabel(c.AttackTargetId) : "a planeswalker").Distinct().ToArray();
                ui.Status.text = "Attacking " + (targets.Length == 1 ? targets[0] : "multiple defenders");
            }
            ui.Status.color=selectable || seat==priority?Aqua:seat==active?Gold:new Color(.68f,.69f,.68f);ui.Accent.color=selectable?Aqua:seat==active?Gold:_focusedSeat==seat?new Color(.78f,.67f,.46f,.7f):new Color(.50f,.48f,.42f,.18f);
            ui.Background.color=selectable?new Color(.03f,.09f,.10f,.9f):_focusedSeat==seat?new Color(.10f,.075f,.035f,.88f):new Color(.015f,.018f,.024f,.82f);
            if (_lanes.TryGetValue(seat, out var lane)) { lane.enabled = Overview && alive && selectable; var color = selectable ? Aqua : seat == active ? Gold : SeatColor(seat); color.a = seat == active || selectable ? .38f : .18f; lane.startColor = lane.endColor = color; }
        }
        string phase = state.CurrentPhase.ToString(); phase = phase == "Main1" ? "First main" : phase == "Main2" ? "Second main" : phase;
        _turn.text = "<size=16>Turn " + state.GameWideTurn + "  /  " + phase + "</size>\n" + Name(active);
        bool applied = _game.WorkflowController.CurrentWorkflow?.AppliedState == InteractionAppliedState.Applied;
        bool waiting = _game.WorkflowController.CurrentWorkflow is IRoundTripWorkflow roundTrip && roundTrip.IsWaitingForRoundTrip();
        _priority.text = !applied || waiting ? "Resolving" : priority == 1 ? "Your decision" : priority > 1 ? Name(priority) + " is deciding" : "Resolving";
        _turnAccent.color=Gold;_viewLabel.text=Rail?(_spectator.Following?"Automatic camera  [Tab]":"Return to automatic  [Tab]"):Overview?"All battlefields  [Tab]":"Return to table  [Tab]";
    }
    private void OnDestroy()
    {
        if (Active == this) Active = null; foreach (var avatar in _avatars) if (avatar.Key != null) { avatar.Key.transform.position = avatar.Value.position; avatar.Key.transform.localScale = avatar.Value.scale; }
        foreach (var zone in _zones) if (zone.Key != null) zone.Key.transform.position = zone.Value.Source; foreach (var box in _zoneColliderSizes) if (box.Key != null) box.Key.size = box.Value; foreach (var effect in _effectScales) if (effect.Key != null) effect.Key.localScale = effect.Value;
        if (_hud != null) UnityEngine.Object.Destroy(_hud); foreach (var lane in _lanes.Values) if (lane != null) UnityEngine.Object.Destroy(lane.gameObject); if (_laneMaterial != null) UnityEngine.Object.Destroy(_laneMaterial);
    }
    private sealed class ZonePose { internal uint Seat; internal Vector3 Source, Delta; }
    private sealed class SeatPanel { internal RectTransform Root = null!; internal Button Button = null!; internal Image Background = null!, Accent = null!, Portrait = null!; internal RectTransform Hand=null!, Library=null!; internal TMP_Text Title = null!, Life = null!, Counts = null!, LibraryCount=null!, Status = null!; internal (RectTransform root, Button button, TMP_Text label) Graveyard, Exile, Target; }
}

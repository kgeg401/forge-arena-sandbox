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

// A shared table for four native players. The hand, stack, card browsers,
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
    private TMP_FontAsset _font = null!;
    private Sprite? _panelOutline;
    private TMP_Text _turn = null!, _priority = null!, _viewLabel = null!;
    private Image _turnAccent = null!;
    private RectTransform _turnPanel = null!, _navPanel = null!, _detailsPanel = null!;
    private int _layoutWidth, _layoutHeight;
    private float _layoutScale;
    private float _nextRefresh;
    private string _lastWorkflow = "";
    private bool _started;
    private uint _focusedSeat;
    private static bool _patched;
    private static readonly FieldInfo HolderGame = AccessTools.Field(typeof(CardHolderBase), "_gameManager");
    private static readonly MethodInfo SetPlayerVisibility = AccessTools.Method(typeof(PlayerFocusController_Quadrant), "SetPlayerVisibility");
    private static readonly Color Gold = new Color(.91f, .66f, .27f, 1), Aqua = new Color(.35f, .84f, .89f, 1);
    private static readonly Color[] SeatColors = { Color.clear, new Color(.78f, .65f, .41f), new Color(.39f, .69f, .88f), new Color(.72f, .52f, .83f), new Color(.39f, .76f, .64f) };
    public int CopiedBoardMeshes => 0;
    public bool Overview => _focusedSeat == 0;
    internal BrowserBase? CurrentBrowser => _game?.BrowserManager?.CurrentBrowser;
    internal bool IsReady => _game != null && _game.CurrentGameState?.Players.Count == 4 && _game.CurrentGameState.GameInfo?.Stage == GameStage.Play;
    internal bool Owns(CardHolderBase holder) => ReferenceEquals(HolderGame.GetValue(holder), _game);
    internal bool Owns(PlayerFocusController_Quadrant focus) => ReferenceEquals(focus, _focus);
    public static void Ensure(GameManager game, PAPA papa, Action showDetails)
    {
        if (game.GetComponent<NativeCommanderPodView>() != null || game.CurrentGameState?.Players.Count != 4) return;
        var view = game.gameObject.AddComponent<NativeCommanderPodView>();
        try { view.Initialize(game, papa, showDetails); } catch { UnityEngine.Object.Destroy(view); throw; }
    }
    private void Initialize(GameManager game, PAPA papa, Action showDetails)
    {
        _game = game; _papa = papa; _showDetails = showDetails;
        _focus = game.Context.Get<IPlayerFocusController>() as PlayerFocusController_Quadrant ?? throw new NotSupportedException("Native four-player camera is unavailable");
        _camera = (Transform)AccessTools.Field(typeof(PlayerFocusController_Quadrant), "_cameraTransform").GetValue(_focus);
        if (!_patched) { NativePodLayoutPatches.Install(); _patched = true; }
        Active = this; BuildControls(); BuildLanes();
    }
    internal static Vector3 NativeOffset(uint seat) => seat == 1 ? Vector3.zero : seat == 2 ? new Vector3(0, 0, -38.1452f) : seat == 3 ? new Vector3(-64.3885f, 0, -38.1452f) : new Vector3(-64.3885f, 0, 0);
    internal float Scale(uint seat, bool battlefield = false) => !Overview ? 1f : battlefield && _battlefieldFit.TryGetValue(seat, out var fit) ? fit : seat == 1 ? .88f : .57f;
    internal void FitBattlefields(List<CardLayoutData> layout)
    {
        // Fit actual generated card extents inside each ownership lane. A full
        // opponent board must never spill into its neighbor's battlefield.
        // This affects presentation only; focus and native hover remain large.
        _battlefieldFit.Clear();
        foreach (var group in layout.Where(d => d.IsVisibleInLayout && d.Card?.Model?.Instance?.Controller != null).GroupBy(d => d.Card.Model.Instance.Controller.InstanceId))
        {
            uint seat = group.Key; if (seat < 1 || seat > 4) continue;
            float extent = 0;
            foreach (var data in group)
            {
                // A collider's diagonal also bounds a tapped or turning card;
                // its local x width alone can under-fit a crowded lane.
                float radius = Vector3.Scale(data.Card.Collider.size, data.Scale).magnitude * .5f;
                extent = Mathf.Max(extent, Mathf.Abs(data.Position.x - NativeOffset(seat).x) + radius);
            }
            float normal = seat == 1 ? .88f : .57f, available = seat == 1 ? 27.5f : 9.8f;
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
        if (seat == 1) p.z += 6;
        else { p.x += seat == 2 ? 21 : seat == 4 ? -21 : 0; p.z -= 1; }
        return p;
    }
    internal void MapEndpoint(CardHolderBase holder, CardLayoutData data, ref IdealPoint endpoint)
    {
        if (!IsReady || !Owns(holder) || data.Card?.Model?.Instance == null) return;
        string kind = holder.CardHolderType.ToString(); var instance = data.Card.Model.Instance;
        uint seat = kind == "Battlefield" ? instance.Controller?.InstanceId ?? 0 : instance.Zone?.OwnerId ?? 0;
        if (seat == 0) seat = instance.Owner?.InstanceId ?? 0;
        if (seat < 1 || seat > 4) return;
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
        if (!IsReady || !Owns(holder) || seat < 1 || seat > 4) return;
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
        foreach (var holder in UnityEngine.Object.FindObjectsByType<ZoneCardHolderBase>(FindObjectsSortMode.None))
        {
            uint seat = holder.GetZone?.OwnerId ?? 0;
            if (holder is PlayerExileCardHolder) seat = (uint)AccessTools.Field(typeof(PlayerExileCardHolder), "_playerId").GetValue(holder);
            PositionZone(holder, seat);
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
        uint seat = _zones.TryGetValue(holder, out var pose) ? pose.Seat : holder.GetZone?.OwnerId ?? 0; if (seat < 1 || seat > 4) return;
        var elements = (Dictionary<string, DuelSceneBrowserElementData>)AccessTools.Field(typeof(BrowserBase), "uiElementData").GetValue(browser);
        string zone = holder.CardHolderType.ToString().ToLowerInvariant();
        foreach (var header in elements.Values.Where(e => e.GameObject != null).SelectMany(e => e.GameObject.GetComponentsInChildren<BrowserHeader>(true)).Distinct())
            header.SetHeaderText((seat == 1 ? "Your" : PlayerLabel(seat) + "'s") + " " + zone);
    }
    public void ShowTable() => SetView(0);
    public void ShowSeat(uint seat)
    {
        if (SelectingAcrossPlayers) return;
        if (_game.CurrentGameState?.GetPlayerById(seat)?.Status != PlayerStatus.InGame) return;
        SetView(_focusedSeat == seat ? 0 : seat);
    }
    private void SetView(uint seat)
    {
        _focusedSeat = seat; var field = AccessTools.Field(typeof(PlayerFocusController_Quadrant), "_focusMode"); field.SetValue(_focus, Enum.Parse(field.FieldType, "All"));
        _game.SplineMovementSystem.AddPermanentGoal(_camera, new IdealPoint(_camera) { Position = CameraPosition(Overview) });
        PositionAvatars(); PositionZones(); AlignHeaders(); foreach (var holder in UnityEngine.Object.FindObjectsByType<CardHolderBase>(FindObjectsSortMode.None)) holder.LayoutNow(); Refresh();
    }
    private static Vector3 CameraPosition(bool table)
    {
        float aspect = Screen.width / (float)Mathf.Max(1, Screen.height), fit = Mathf.Max(1, (16f / 9) / aspect);
        return (table ? new Vector3(0, 70, 29) : new Vector3(0, 50.5f, 19)) * fit;
    }
    private void AlignHeaders()
    {
        var camera = Camera.main; if (camera == null || _seats.Count != 4) return;
        _layoutWidth = Screen.width; _layoutHeight = Screen.height;
        float scale = _hud.GetComponent<Canvas>().scaleFactor; if (scale <= 0) return; _layoutScale = scale;
        var delta = CameraPosition(true) - _camera.position; var centers = new Dictionary<uint, float>();
        foreach (uint seat in new uint[] { 2, 3, 4 })
        {
            float x = seat == 2 ? 21 : seat == 4 ? -21 : 0;
            var original = _avatars.FirstOrDefault(p => p.Key != null && p.Key.InstanceId == seat);
            var point = original.Key != null ? original.Value.position - NativeOffset(seat) : new Vector3(0, 3.69f, -11.33f);
            point.x = point.x * .57f + x; point.z = point.z * .57f - 1;
            centers[seat] = camera.WorldToScreenPoint(point - delta).x;
        }
        float gap = Mathf.Min(centers[3] - centers[2], centers[4] - centers[3]);
        float width = Mathf.Min(426, Mathf.Max(270, (gap - 24) / scale));
        foreach (uint seat in new uint[] { 2, 3, 4 })
        {
            var ui = _seats[seat]; ui.Root.anchorMin = ui.Root.anchorMax = new Vector2(centers[seat] / Screen.width, 1); ui.Root.anchoredPosition = new Vector2(0, -16); ui.Root.sizeDelta = new Vector2(width, 108);
            ui.Title.rectTransform.sizeDelta = new Vector2(width - 108, 33); ui.Status.rectTransform.sizeDelta = new Vector2(width - 28, 24); AlignZoneRow(ui);
        }
        float side = Mathf.Min(216, Mathf.Max(160, (centers[2] - width * scale * .5f - 18) / scale - 22));
        foreach (var panel in new[] { _navPanel, _turnPanel, _detailsPanel })
        {
            if (panel == null) continue; panel.sizeDelta = new Vector2(side, panel.sizeDelta.y);
            foreach (var text in panel.GetComponentsInChildren<TMP_Text>(true)) text.rectTransform.sizeDelta = new Vector2(side - 12, text.rectTransform.sizeDelta.y);
        }
    }
    private void PositionAvatars()
    {
        foreach (var avatar in _game.ViewManager.GetAllAvatars())
        {
            if (!_avatars.TryGetValue(avatar, out var original)) { original = (avatar.transform.position, avatar.transform.localScale); _avatars[avatar] = original; }
            var p = MapPoint(original.position, avatar.InstanceId);
            avatar.transform.position = p; avatar.transform.localScale = original.scale * (Overview ? (avatar.InstanceId == 1 ? .88f : .70f) : 1f);
        }
    }
    private void BuildControls()
    {
        // Asset-load order changes after native dialogs and scene switches.
        // Select the owned title face explicitly instead of the first text's
        // font, which can otherwise be a generic sans-serif fallback.
        _font = Resources.FindObjectsOfTypeAll<TMP_FontAsset>().FirstOrDefault(f => f.name == "Font_Title_SmallCaps") ?? throw new NotSupportedException("The installed Arena small-caps font is unavailable");
        _panelOutline = Resources.FindObjectsOfTypeAll<Sprite>().FirstOrDefault(s => s.name == "deckPanel_Outline");
        _hud = new GameObject("Commander pod shared table", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster)); _hud.transform.SetParent(_game.transform, false);
        var canvas = _hud.GetComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay; canvas.sortingOrder = 31000;
        var scaler = _hud.GetComponent<CanvasScaler>(); scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize; scaler.referenceResolution = new Vector2(1920, 1080); scaler.matchWidthOrHeight = .5f;
        for (uint seat = 2; seat <= 4; seat++) BuildSeat(seat, new Vector2(.25f + (seat - 2) * .25f, 1), new Vector2(0, -16), new Vector2(426, 108));
        BuildSeat(1, new Vector2(0, 0), new Vector2(24, 126), new Vector2(360, 110));
        var turnPanel = Panel("Turn and priority", _hud.transform, new Vector2(0, 1), new Vector2(22, -120), new Vector2(216, 154), new Color(.025f, .035f, .045f, .94f));
        _turnPanel = turnPanel;
        _turnAccent = Panel("Turn accent", turnPanel, new Vector2(0, .5f), Vector2.zero, new Vector2(4, 154), Gold).GetComponent<Image>();
        _turn = Text("Turn", turnPanel, new Vector2(.5f, 1), new Vector2(0, -12), new Vector2(202, 100), 22, TextAlignmentOptions.Center);
        _priority = Text("Priority", turnPanel, new Vector2(.5f, 0), new Vector2(0, 13), new Vector2(202, 23), 18, TextAlignmentOptions.Center); _priority.color = Aqua;
        _priority.enableAutoSizing = true; _priority.fontSizeMin = 12; _priority.fontSizeMax = 18;
        var nav = Panel("Table navigation", _hud.transform, new Vector2(0, 1), new Vector2(22, -20), new Vector2(216, 84), new Color(.025f, .035f, .045f, .94f));
        _navPanel = nav;
        ClickArea(nav, ShowTable); Text("All players", nav, new Vector2(.5f, 1), new Vector2(0, -11), new Vector2(204, 29), 25, TextAlignmentOptions.Center);
        _viewLabel = Text("View", nav, new Vector2(.5f, 0), new Vector2(0, 12), new Vector2(204, 23), 17, TextAlignmentOptions.Center);
        _viewLabel.enableAutoSizing = true; _viewLabel.fontSizeMin = 12; _viewLabel.fontSizeMax = 17;
        var details = Panel("Pod details", _hud.transform, new Vector2(0, 1), new Vector2(22, -292), new Vector2(216, 46), new Color(.025f, .035f, .045f, .94f)); ClickArea(details, _showDetails);
        _detailsPanel = details;
        var detailText = Text("Commander damage [F5]", details, new Vector2(.5f, .5f), Vector2.zero, new Vector2(208, 31), 17, TextAlignmentOptions.Center); detailText.enableAutoSizing = true; detailText.fontSizeMin = 11; detailText.fontSizeMax = 17; _hud.SetActive(false);
    }
    private void BuildSeat(uint seat, Vector2 anchor, Vector2 position, Vector2 size)
    {
        var panel = Panel("Commander pod seat " + seat, _hud.transform, anchor, position, size, new Color(.025f, .035f, .045f, .94f));
        if (seat != 1) panel.pivot = new Vector2(.5f, 1);
        var accent = Panel("Seat color", panel, new Vector2(0, .5f), Vector2.zero, new Vector2(4, size.y), SeatColors[seat]); uint selected = seat; var button = ClickArea(panel, () => ClickSeat(selected));
        var title = Text("Name", panel, new Vector2(0, 1), new Vector2(18, -10), new Vector2(size.x - 108, 33), 25, TextAlignmentOptions.MidlineLeft); title.enableAutoSizing = true; title.fontSizeMin = 18; title.fontSizeMax = 25; title.overflowMode = TextOverflowModes.Ellipsis;
        var life = Text("Life", panel, new Vector2(1, 1), new Vector2(-12, -7), new Vector2(68, 44), 36, TextAlignmentOptions.MidlineRight); life.enableAutoSizing = true; life.fontSizeMin = 10; life.fontSizeMax = 36;
        var counts = Text("Public zone counts", panel, new Vector2(0, 1), new Vector2(18, -43), new Vector2(size.x - 28, 25), 19, TextAlignmentOptions.MidlineLeft);
        counts.enableAutoSizing = true; counts.fontSizeMin = 14; counts.fontSizeMax = 19; counts.overflowMode = TextOverflowModes.Ellipsis;
        var status = Text("Status", panel, new Vector2(0, 0), new Vector2(18, 9), new Vector2(size.x - 28, 22), 18, TextAlignmentOptions.MidlineLeft);
        status.enableAutoSizing = true; status.fontSizeMin = 14; status.fontSizeMax = 18; status.overflowMode = TextOverflowModes.Ellipsis;
        var graveyard = ZoneButton(panel, "Graveyard", () => OpenPublicZone(selected, ZoneType.Graveyard));
        var exile = ZoneButton(panel, "Exile", () => OpenPublicZone(selected, ZoneType.Exile));
        var ui = new SeatPanel { Root = panel, Button = button, Background = panel.GetComponent<Image>(), Accent = accent.GetComponent<Image>(), Title = title, Life = life, Counts = counts, Status = status, Graveyard = graveyard, Exile = exile };
        _seats[seat] = ui; AlignZoneRow(ui);
    }
    private (RectTransform root, Button button, TMP_Text label) ZoneButton(Transform parent, string name, Action action)
    {
        var root = Panel(name + " public zone", parent, new Vector2(0, 1), Vector2.zero, new Vector2(100, 27), Color.clear);
        var label = Text(name + " count", root, new Vector2(0, .5f), Vector2.zero, new Vector2(100, 27), 19, TextAlignmentOptions.MidlineLeft);
        label.enableAutoSizing = true; label.fontSizeMin = 14; label.fontSizeMax = 19; label.overflowMode = TextOverflowModes.Ellipsis;
        var button = ClickArea(root, action); button.targetGraphic = label; button.transition = Selectable.Transition.ColorTint;
        var colors = button.colors; colors.normalColor = new Color(.92f, .91f, .87f); colors.highlightedColor = Gold; colors.selectedColor = colors.normalColor; colors.pressedColor = Aqua; colors.disabledColor = new Color(.56f, .60f, .62f); button.colors = colors;
        return (root, button, label);
    }
    private static void AlignZoneRow(SeatPanel ui)
    {
        float width = ui.Root.sizeDelta.x - 28;
        ui.Counts.rectTransform.sizeDelta = new Vector2(width * .46f - 8, 25);
        ui.Graveyard.root.anchoredPosition = new Vector2(21 + width * .46f, -42); ui.Graveyard.root.sizeDelta = new Vector2(width * .34f - 8, 27); ui.Graveyard.label.rectTransform.sizeDelta = ui.Graveyard.root.sizeDelta;
        ui.Exile.root.anchoredPosition = new Vector2(21 + width * .80f, -42); ui.Exile.root.sizeDelta = new Vector2(width * .20f - 3, 27); ui.Exile.label.rectTransform.sizeDelta = ui.Exile.root.sizeDelta;
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
        if (_panelOutline != null && size.x >= 180 && size.y >= 40)
        {
            var border = new GameObject("Native Arena panel outline", typeof(RectTransform), typeof(Image)); var rect = (RectTransform)border.transform; rect.SetParent(r, false); rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one; rect.offsetMin = rect.offsetMax = Vector2.zero;
            var frame = border.GetComponent<Image>(); frame.sprite = _panelOutline; frame.type = Image.Type.Sliced; frame.color = new Color(.65f, .61f, .51f, .55f); frame.raycastTarget = false;
        }
        return r;
    }
    private TMP_Text Text(string name, Transform parent, Vector2 anchor, Vector2 position, Vector2 size, float fontSize, TextAlignmentOptions alignment)
    {
        var obj = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI)); var r = (RectTransform)obj.transform; r.SetParent(parent, false); r.anchorMin = r.anchorMax = anchor; r.pivot = anchor; r.anchoredPosition = position; r.sizeDelta = new Vector2(size.x, Mathf.Max(size.y, fontSize * 1.3f));
        var text = obj.GetComponent<TextMeshProUGUI>(); text.font = _font; text.fontSize = fontSize; text.text = name; text.color = new Color(.92f, .91f, .87f); text.alignment = alignment; text.raycastTarget = false; text.textWrappingMode = TextWrappingModes.NoWrap; text.overflowMode = TextOverflowModes.Overflow; return text;
    }
    private static Button ClickArea(RectTransform panel, Action action)
    {
        panel.GetComponent<Image>().raycastTarget = true; var button = panel.gameObject.AddComponent<Button>(); button.targetGraphic = panel.GetComponent<Image>(); button.transition = Selectable.Transition.None; button.onClick.AddListener(() => action()); return button;
    }
    private void BuildLanes()
    {
        var shader = Shader.Find("Sprites/Default"); if (shader == null) return;
        _laneMaterial = new Material(shader);
        for (uint seat = 1; seat <= 4; seat++)
        {
            var obj = new GameObject("Commander pod lane " + seat); obj.transform.SetParent(_game.transform, false);
            var line = obj.AddComponent<LineRenderer>(); line.sharedMaterial = _laneMaterial; line.useWorldSpace = true; line.loop = true; line.positionCount = 4; line.startWidth = line.endWidth = .075f;
            float center = seat == 2 ? 21 : seat == 4 ? -21 : 0; float half = seat == 1 ? 28 : 10.2f, near = seat == 1 ? 21 : 1, far = seat == 1 ? 3 : -18;
            line.SetPositions(new[] { new Vector3(center - half, .65f, far), new Vector3(center + half, .65f, far), new Vector3(center + half, .65f, near), new Vector3(center - half, .65f, near) }); _lanes[seat] = line;
        }
    }
    private bool CanSelectPlayer(uint seat)
    {
        var workflow = _game.WorkflowController.CurrentWorkflow as IClickableWorkflow;
        var avatar = _game.ViewManager.GetAllAvatars().SingleOrDefault(v => v.InstanceId == seat);
        return workflow != null && _game.WorkflowController.CurrentWorkflow.AppliedState == InteractionAppliedState.Applied && avatar != null && workflow.CanClick(avatar, SimpleInteractionType.Primary);
    }
    private bool SelectingAcrossPlayers
    {
        get { string name = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? ""; return name.IndexOf("Target", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("Attack", StringComparison.OrdinalIgnoreCase) >= 0 || name.IndexOf("Block", StringComparison.OrdinalIgnoreCase) >= 0 || _game.CurrentGameState.Players.Any(p => CanSelectPlayer(p.InstanceId)); }
    }
    private void ClickSeat(uint seat)
    {
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
        if (_game == null || _hud == null) return; bool play = IsReady && _game.Context.Get<IDuelSceneStateProvider>().CurrentState.Value.AllowInput && !_game.BrowserManager.IsBrowserVisible && !_game.Context.Get<SettingsMenuHost>().IsOpen(); _hud.SetActive(play); if (!play) { foreach (var lane in _lanes.Values) lane.enabled = false; return; }
        if (!_started) { _started = true; ShowTable(); }
        if (!Overview && _game.CurrentGameState.GetPlayerById(_focusedSeat)?.Status != PlayerStatus.InGame) ShowTable();
        if (Screen.width != _layoutWidth || Screen.height != _layoutHeight || Mathf.Abs(_hud.GetComponent<Canvas>().scaleFactor - _layoutScale) > .001f) SetView(_focusedSeat);
        var keyboard = Keyboard.current;
        if (keyboard != null && Application.isFocused)
        {
            if (keyboard.tabKey.wasPressedThisFrame) ShowTable(); else if (keyboard.f1Key.wasPressedThisFrame) ShowSeat(1); else if (keyboard.f2Key.wasPressedThisFrame) ShowSeat(2); else if (keyboard.f3Key.wasPressedThisFrame) ShowSeat(3); else if (keyboard.f4Key.wasPressedThisFrame) ShowSeat(4); else if (keyboard.f5Key.wasPressedThisFrame) _showDetails();
        }
        string workflow = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? "";
        if (workflow != _lastWorkflow) { _lastWorkflow = workflow; if (!Overview && (workflow.IndexOf("Target", StringComparison.OrdinalIgnoreCase) >= 0 || workflow.IndexOf("Attack", StringComparison.OrdinalIgnoreCase) >= 0 || workflow.IndexOf("Block", StringComparison.OrdinalIgnoreCase) >= 0)) ShowTable(); }
        if (!Overview && SelectingAcrossPlayers) ShowTable();
        if (Time.unscaledTime >= _nextRefresh) { _nextRefresh = Time.unscaledTime + .15f; Refresh(); }
    }
    private void LateUpdate()
    {
        if (!IsReady) return; PositionAvatars();
        // The original quadrant names otherwise float down the left edge.
        foreach (uint seat in new uint[] { 1, 2, 3, 4 }) SetPlayerVisibility.Invoke(_focus, new object[] { seat, false });
    }
    private void Refresh()
    {
        if (_turn == null) return; var state = _game.CurrentGameState; if (state == null) return; uint active = state.ActivePlayer?.InstanceId ?? 0, priority = state.DecidingPlayer?.InstanceId ?? 0;
        string workflowName = _game.WorkflowController.CurrentWorkflow?.GetType().Name ?? "";
        bool declaringAttacks = workflowName.IndexOf("DeclareAttack", StringComparison.OrdinalIgnoreCase) >= 0;
        var attacks = state.Battlefield.VisibleCards.Where(c => c.Controller != null && c.Zone?.Type == ZoneType.Battlefield && state.Battlefield.CardIds.Contains(c.InstanceId) && c.AttackState != AttackState.None && c.AttackTargetId != 0).ToArray();
        string Name(uint seat) => PlayerLabel(seat);
        foreach (var entry in _seats)
        {
            uint seat = entry.Key; var ui = entry.Value; var player = state.GetPlayerById(seat); bool alive = player?.Status == PlayerStatus.InGame;
            ui.Title.text = seat + "  " + Name(seat); ui.Life.text = alive ? player!.LifeTotal.ToString() : "OUT";
            int Count(ZoneType zone) => zone == ZoneType.Exile ? state.Exile.VisibleCards.Count(c => c.Owner?.InstanceId == seat) : (int)(state.GetZoneForPlayer(seat, zone)?.TotalCardCount ?? 0);
            ui.Counts.text = alive ? "Hand " + Count(ZoneType.Hand) + "   Library " + Count(ZoneType.Library) : "Eliminated · seat retained";
            ui.Counts.rectTransform.sizeDelta = new Vector2((ui.Root.sizeDelta.x - 28) * (alive ? .46f : 1) - (alive ? 8 : 0), 25);
            int graveyard = Count(ZoneType.Graveyard), exile = Count(ZoneType.Exile);
            ui.Graveyard.root.gameObject.SetActive(alive); ui.Exile.root.gameObject.SetActive(alive);
            ui.Graveyard.label.text = graveyard > 0 ? "<u>Graveyard " + graveyard + "</u>" : "Graveyard 0"; ui.Graveyard.button.interactable = alive && graveyard > 0;
            ui.Exile.label.text = exile > 0 ? "<u>Exile " + exile + "</u>" : "Exile 0"; ui.Exile.button.interactable = alive && exile > 0;
            ui.Graveyard.root.GetComponent<Image>().raycastTarget = ui.Graveyard.button.interactable; ui.Exile.root.GetComponent<Image>().raycastTarget = ui.Exile.button.interactable;
            bool selectable = alive && CanSelectPlayer(seat);
            ui.Button.interactable = alive && (!SelectingAcrossPlayers || selectable);
            ui.Status.text = !alive ? "Out of this game" : selectable ? (declaringAttacks ? "ATTACK THIS PLAYER" : "TARGET THIS PLAYER") : SelectingAcrossPlayers ? (declaringAttacks ? "Choose an attacker below" : "Select on the table") : seat == active ? (seat == priority ? "TURN · HAS PRIORITY" : "CURRENT TURN") : seat == priority ? "HAS PRIORITY" : _focusedSeat == seat ? "Focused · click to return to table" : Overview && Scale(seat, true) < .5f ? "Dense board · click to focus  [F" + seat + "]" : "Click to focus  [F" + seat + "]";
            var incoming = attacks.Where(c => c.AttackTargetId == seat).ToArray(); var outgoing = attacks.Where(c => c.Controller.InstanceId == seat).ToArray();
            if (alive && !selectable && incoming.Length > 0) ui.Status.text = incoming.Length + " attacker" + (incoming.Length == 1 ? "" : "s") + " from " + string.Join(", ", incoming.Select(c => PlayerLabel(c.Controller.InstanceId)).Distinct());
            else if (alive && !selectable && outgoing.Length > 0)
            {
                var targets = outgoing.Select(c => c.AttackTargetId <= 4 ? PlayerLabel(c.AttackTargetId) : "a planeswalker").Distinct().ToArray();
                ui.Status.text = "Attacking " + (targets.Length == 1 ? targets[0] : "multiple defenders");
            }
            ui.Status.color = selectable || seat == priority ? Aqua : seat == active ? Gold : new Color(.68f, .72f, .74f); ui.Accent.color = selectable ? Aqua : seat == active ? Gold : SeatColors[seat];
            ui.Background.color = !alive ? new Color(.04f, .04f, .04f, .88f) : selectable ? new Color(.035f, .14f, .15f, .96f) : _focusedSeat == seat ? new Color(.12f, .10f, .06f, .96f) : new Color(.025f, .035f, .045f, .94f);
            if (_lanes.TryGetValue(seat, out var lane)) { lane.enabled = Overview && alive; var color = selectable ? Aqua : seat == active ? Gold : SeatColors[seat]; color.a = seat == active || selectable ? .38f : .18f; lane.startColor = lane.endColor = color; }
        }
        string phase = state.CurrentPhase.ToString(); phase = phase == "Main1" ? "First main" : phase == "Main2" ? "Second main" : phase;
        _turn.text = "TURN " + state.GameWideTurn + "\n<size=29>" + Name(active) + "</size>\n" + phase;
        bool applied = _game.WorkflowController.CurrentWorkflow?.AppliedState == InteractionAppliedState.Applied;
        bool waiting = _game.WorkflowController.CurrentWorkflow is IRoundTripWorkflow roundTrip && roundTrip.IsWaitingForRoundTrip();
        _priority.text = !applied || waiting ? "Resolving" : priority == 1 ? "Your decision" : priority > 1 ? Name(priority) + " is deciding" : "Resolving";
        _turnAccent.color = active >= 1 && active <= 4 ? SeatColors[active] : Gold; _viewLabel.text = Overview ? "Table view  [Tab]" : "Viewing " + Name(_focusedSeat) + " · back [Tab]";
    }
    private void OnDestroy()
    {
        if (Active == this) Active = null; foreach (var avatar in _avatars) if (avatar.Key != null) { avatar.Key.transform.position = avatar.Value.position; avatar.Key.transform.localScale = avatar.Value.scale; }
        foreach (var zone in _zones) if (zone.Key != null) zone.Key.transform.position = zone.Value.Source; foreach (var box in _zoneColliderSizes) if (box.Key != null) box.Key.size = box.Value; foreach (var effect in _effectScales) if (effect.Key != null) effect.Key.localScale = effect.Value;
        if (_hud != null) UnityEngine.Object.Destroy(_hud); foreach (var lane in _lanes.Values) if (lane != null) UnityEngine.Object.Destroy(lane.gameObject); if (_laneMaterial != null) UnityEngine.Object.Destroy(_laneMaterial);
    }
    private sealed class ZonePose { internal uint Seat; internal Vector3 Source, Delta; }
    private sealed class SeatPanel { internal RectTransform Root = null!; internal Button Button = null!; internal Image Background = null!, Accent = null!; internal TMP_Text Title = null!, Life = null!, Counts = null!, Status = null!; internal (RectTransform root, Button button, TMP_Text label) Graveyard, Exile; }
}

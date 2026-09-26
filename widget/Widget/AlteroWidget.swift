import SwiftUI
import WidgetKit

struct Entry: TimelineEntry {
    var date: Date
    let snapshot: Snapshot?
    /// Raw stored page; normalized against the current page list at render.
    let pageIndex: Int
    /// Raw stored navigation; resolved against the snapshot at render.
    var nav = NavState()
    /// The last auto-switch toggle request; resolved against the snapshot at
    /// render.
    var pendingToggle: PendingToggle?
    /// The last switch request; resolved against the snapshot at render.
    var pendingSwitch: PendingSwitch?
    /// When the host app last started the backend (its marker file).
    var backendStartedAt: Date?
    /// The host app's last failed start (its failure marker).
    var backendFailure: BackendStart.FailureNote?
    let appearance: AppearanceOption
}

struct Provider: AppIntentTimelineProvider {
    // The gallery (and the redacted placeholder) draw the sample, never the
    // user's own accounts: a snapshot file may be missing, and if present it
    // holds real account names.
    func placeholder(in context: Context) -> Entry {
        Entry(date: .now, snapshot: Self.sample(), pageIndex: 0, appearance: .system)
    }

    func snapshot(for configuration: AlteroConfigIntent, in context: Context) async -> Entry {
        guard context.isPreview else { return entry(configuration, context) }
        return Entry(date: .now, snapshot: Self.sample(), pageIndex: 0, appearance: configuration.appearance)
    }

    /// The Python producer's golden fixture (example.com accounts), bundled
    /// as a resource and moved to now.
    private static func sample() -> Snapshot? {
        guard let url = Bundle.main.url(forResource: "snapshot_golden", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? Snapshot.decode(data, takenAt: .now)
    }

    func timeline(for configuration: AlteroConfigIntent, in context: Context) async -> Timeline<Entry> {
        // One entry, plus one per moment a pending request changes the
        // drawing on its own (a toggle, switch or start timing out): every
        // ticking thing on screen is a `Text(date:style:)` driven by an
        // absolute `resetsAt`, so WidgetKit ticks the countdowns itself. The
        // reload is what picks up a newer snapshot file (and refreshes the
        // human "3d 11h" countdowns).
        // 60s matches the backend's own poll interval: asking for less would
        // only re-read a file that cannot have changed. WidgetKit budgets
        // reloads and may serve them less often than requested -- this is the
        // ceiling, not a guarantee.
        let now = Date.now
        let first = entry(configuration, context, at: now)
        let reload = now.addingTimeInterval(60)
        let expiries = Set([
            AutoswitchToggle.expiry(of: first.pendingToggle, now: now),
            AccountSwitch.expiry(of: first.pendingSwitch, now: now),
            BackendStart.expiry(markerAt: first.backendStartedAt, failure: first.backendFailure, now: now)
        ].compactMap { $0 }.filter { $0 < reload }).sorted()
        var entries = [first]
        for date in expiries {
            var next = first
            next.date = date
            entries.append(next)
        }
        let policy = expiries.first.map { min(reload, $0.addingTimeInterval(1)) } ?? reload
        return Timeline(entries: entries, policy: .after(policy))
    }

    private func entry(_ configuration: AlteroConfigIntent, _ context: Context, at date: Date = .now) -> Entry {
        let family = LayoutFamily(context.family)
        return Entry(date: date,
                     snapshot: SnapshotFile.load(),
                     pageIndex: PageStore.index(family),
                     nav: NavStore.state(family),
                     pendingToggle: AutoswitchStore.pending(),
                     pendingSwitch: SwitchStore.pending(),
                     backendStartedAt: SnapshotFile.loadBackendStart(),
                     backendFailure: SnapshotFile.loadBackendFailure(),
                     appearance: configuration.appearance)
    }
}

/// Applies the per-widget Appearance and the container background.
struct WidgetRoot: View {
    let entry: Entry
    @Environment(\.colorScheme) private var systemScheme
    @Environment(\.widgetRenderingMode) private var renderingMode

    var body: some View {
        let scheme: ColorScheme = switch entry.appearance {
        case .system: systemScheme
        case .light: .light
        case .dark: .dark
        }
        AlteroWidgetView(entry: entry)
            // On macOS 26, containerBackground's Liquid Glass material is
            // drawn following the real host appearance, not the environment
            // this view forces below -- so a forced (or mismatched system)
            // scheme's text could sit on a container tinted for the other
            // one. Painting the same background inside the normal content
            // pass, full-color only, keeps it resolving under `scheme` right
            // alongside the text. containerBackground stays so accented and
            // vibrant rendering -- which drop this layer along with it -- are
            // unaffected, and so the system still has one to fall back to.
            .background { if renderingMode == .fullColor { background(scheme) } }
            .containerBackground(for: .widget) { background(scheme) }
            .environment(\.colorScheme, scheme)
    }

    /// System: the window background, mostly opaque. A lighter fill let
    /// Liquid Glass wash the text out on a light desktop; this keeps a hint
    /// of the desktop behind it. Accented and vibrant rendering drop the
    /// container background, so those modes are unaffected.
    /// Forced modes: the glass still follows the system appearance, so they
    /// lay their own light/dark tint over it to keep the forced text legible.
    /// Every case is a concrete color picked from `scheme`, never a semantic
    /// style: the semantic `.background` is archived unresolved and resolved
    /// by the host at display time, so a render kept around past an
    /// appearance change (the widget gallery's preview) paired text drawn
    /// for one scheme with a background drawn for the other.
    private func background(_ scheme: ColorScheme) -> Color {
        switch entry.appearance {
        case .system: (scheme == .dark ? Self.darkWindow : Self.lightWindow).opacity(0.88)
        case .light: Color.white.opacity(0.88)
        case .dark: Color(white: 0.11).opacity(0.88)
        }
    }

    /// The window background color, resolved once per appearance.
    private static let lightWindow = windowBackground(.aqua)
    private static let darkWindow = windowBackground(.darkAqua)

    private static func windowBackground(_ name: NSAppearance.Name) -> Color {
        var color = name == .darkAqua ? Color(white: 0.11) : .white
        NSAppearance(named: name)?.performAsCurrentDrawingAppearance {
            if let rgb = NSColor.windowBackgroundColor.usingColorSpace(.sRGB) {
                color = Color(.sRGB, red: rgb.redComponent, green: rgb.greenComponent, blue: rgb.blueComponent)
            }
        }
        return color
    }
}

struct AlteroWidget: Widget {
    // chronod caches the descriptor per (extension bundle id, kind) and keeps
    // serving the old display name, so a rename changes both.
    nonisolated static let kind = "AlteroWidget"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: Self.kind, intent: AlteroConfigIntent.self, provider: Provider()) { entry in
            WidgetRoot(entry: entry)
        }
        .configurationDisplayName("Altero")
        .description("Claude account usage at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge, .systemExtraLarge])
        .contentMarginsDisabled()
    }
}

// MARK: - Previews
//
// WidgetRoot is previewed directly (not through the `#Preview(as:)` widget
// macro) because that macro has no way to force a colorScheme or
// widgetRenderingMode; a plain View preview does, via .environment, framed
// at the macOS widget sizes (#Preview ignores .previewContext).

#if DEBUG
private func previewEntry() -> Entry {
    Entry(date: .now, snapshot: nil, pageIndex: 0, appearance: .system)
}

#Preview("Large - system light - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 364, height: 382)
}

#Preview("Large - system dark - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .dark)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 364, height: 382)
}

#Preview("Large - system light - accented") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .accented)
        .frame(width: 364, height: 382)
}

#Preview("Large - system light - vibrant") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .vibrant)
        .frame(width: 364, height: 382)
}

#Preview("Small - system light - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 170, height: 170)
}

#Preview("Small - system dark - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .dark)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 170, height: 170)
}

#Preview("Medium - system light - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 364, height: 170)
}

#Preview("Medium - system dark - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .dark)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 364, height: 170)
}

#Preview("ExtraLarge - system light - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .light)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 758, height: 382)
}

#Preview("ExtraLarge - system dark - full color") {
    WidgetRoot(entry: previewEntry())
        .environment(\.colorScheme, .dark)
        .environment(\.widgetRenderingMode, .fullColor)
        .frame(width: 758, height: 382)
}
#endif

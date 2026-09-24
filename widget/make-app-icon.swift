#!/usr/bin/env swift
// Draws Altero.app's icon and writes the host target's AppIcon set.
//
//   swift widget/make-app-icon.swift [output directory]
//
// Default output is App/Assets.xcassets/AppIcon.appiconset, PNGs plus the
// Contents.json that lists them -- one file describes both, so the slot list
// below cannot drift from the catalog. The PNGs are committed; this script is
// how they are regenerated, not a build step.
//
// The artwork is "another you": two identical busts, the second standing just
// behind and beside the first -- the account that takes over. A midnight
// plate, the front figure in off-white, the one behind in the widget's clay
// accent, deepened. Everything is laid out on a 1024pt canvas and scaled, so
// every size is the same drawing.

import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

// MARK: - Canvas

/// Apple's macOS icon grid: the artwork is a 824pt rounded square centred in a
/// 1024pt canvas. Filling the canvas edge to edge would render the icon
/// visibly larger than every system icon beside it.
let canvas: CGFloat = 1024
let artwork: CGFloat = 824
let center = CGPoint(x: canvas / 2, y: canvas / 2)

/// The macOS icon shape is a continuous-corner square, not a rounded
/// rectangle; a superellipse of degree 5 is the usual close approximation.
func squirclePath(side: CGFloat, center: CGPoint) -> CGPath {
    let radius = side / 2
    let exponent: CGFloat = 2.0 / 5.0
    let path = CGMutablePath()
    let steps = 720
    for step in 0...steps {
        let angle = CGFloat(step) / CGFloat(steps) * 2 * .pi
        let cosine = cos(angle), sine = sin(angle)
        let point = CGPoint(
            x: center.x + radius * copysign(pow(abs(cosine), exponent), cosine),
            y: center.y + radius * copysign(pow(abs(sine), exponent), sine))
        if step == 0 { path.move(to: point) } else { path.addLine(to: point) }
    }
    path.closeSubpath()
    return path
}

// MARK: - Palette

func color(_ hex: UInt32, alpha: CGFloat = 1) -> CGColor {
    CGColor(
        srgbRed: CGFloat((hex >> 16) & 0xFF) / 255,
        green: CGFloat((hex >> 8) & 0xFF) / 255,
        blue: CGFloat(hex & 0xFF) / 255,
        alpha: alpha)
}

/// Each fill is a top-to-bottom pair: a little light from above, no more.
let plateColors = [color(0x2E3350), color(0x151827)]    // midnight indigo
let frontColors = [color(0xFFFDF8), color(0xE8E1D3)]    // off-white
let behindColors = [color(0xDC8A6C), color(0x9C4032)]   // the widget's clay, deeper and rosier

// MARK: - Figures

/// A bust: a round head over a rounded shoulder line that runs off the plate's
/// bottom edge. Both busts are this one shape, only moved -- the same person.
struct Bust {
    var headX: CGFloat
    var headY: CGFloat   // the head's centre

    static let head: CGFloat = 122       // radius
    static let neck: CGFloat = 30        // gap between head and shoulders
    static let shoulderWidth: CGFloat = 500
    static let shoulderRise: CGFloat = 190  // shoulder top above the curve's base

    var headPath: CGPath {
        CGPath(ellipseIn: CGRect(
            x: headX - Bust.head, y: headY - Bust.head, width: 2 * Bust.head, height: 2 * Bust.head),
            transform: nil)
    }

    var shoulderPath: CGPath {
        let top = headY - Bust.head - Bust.neck
        let base = top - Bust.shoulderRise
        let half = Bust.shoulderWidth / 2
        let path = CGMutablePath()
        path.move(to: CGPoint(x: headX - half, y: 0))
        path.addLine(to: CGPoint(x: headX - half, y: base))
        // Two quarter-ellipses meeting at the top: round, not domed.
        path.addCurve(
            to: CGPoint(x: headX, y: top),
            control1: CGPoint(x: headX - half, y: base + Bust.shoulderRise * 0.56),
            control2: CGPoint(x: headX - half * 0.56, y: top))
        path.addCurve(
            to: CGPoint(x: headX + half, y: base),
            control1: CGPoint(x: headX + half * 0.56, y: top),
            control2: CGPoint(x: headX + half, y: base + Bust.shoulderRise * 0.56))
        path.addLine(to: CGPoint(x: headX + half, y: 0))
        path.closeSubpath()
        return path
    }

    var path: CGPath {
        let path = CGMutablePath()
        path.addPath(headPath)
        path.addPath(shoulderPath)
        return path
    }
}

/// The one in front sits left of centre; the other stands behind, up and to
/// the right, so its head and shoulder show clearly past the first.
let front = Bust(headX: 432, headY: 578)
let behind = Bust(headX: 602, headY: 660)
/// The plate-coloured gap cut around the front figure, so the two read as two
/// even where their colours are close.
let separation: CGFloat = 34

// MARK: - Drawing

func fillGradient(_ path: CGPath, _ colors: [CGColor], in context: CGContext, top: CGFloat, bottom: CGFloat) {
    context.saveGState()
    context.addPath(path)
    context.clip()
    let gradient = CGGradient(colorsSpace: nil, colors: colors as CFArray, locations: [0, 1])!
    context.drawLinearGradient(
        gradient, start: CGPoint(x: 0, y: top), end: CGPoint(x: 0, y: bottom),
        options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
    context.restoreGState()
}

func draw(into context: CGContext) {
    let plate = squirclePath(side: artwork, center: center)
    let plateTop = center.y + artwork / 2, plateBottom = center.y - artwork / 2

    // The plate, with the soft drop shadow every Big Sur icon carries.
    context.saveGState()
    context.setShadow(offset: CGSize(width: 0, height: -10), blur: 28, color: color(0x000000, alpha: 0.35))
    context.addPath(plate)
    context.setFillColor(plateColors[1])
    context.fillPath()
    context.restoreGState()
    fillGradient(plate, plateColors, in: context, top: plateTop, bottom: plateBottom)

    context.saveGState()
    context.addPath(plate)
    context.clip()
    // A soft glow high on the plate, behind the heads: depth, not a feature.
    let glow = CGGradient(
        colorsSpace: nil, colors: [color(0x6A74B0, alpha: 0.35), color(0x6A74B0, alpha: 0)] as CFArray,
        locations: [0, 1])!
    context.drawRadialGradient(
        glow, startCenter: CGPoint(x: 540, y: 700), startRadius: 0,
        endCenter: CGPoint(x: 540, y: 700), endRadius: 460, options: [])

    // The figure behind, with the front figure's outline cut out of it. The
    // cut happens inside a transparency layer, so it clears only this figure
    // and the plate shows through.
    context.beginTransparencyLayer(auxiliaryInfo: nil)
    fillGradient(behind.path, behindColors, in: context, top: behind.headY + Bust.head, bottom: plateBottom)
    context.setBlendMode(.clear)
    context.addPath(front.path)
    context.fillPath()
    context.setLineWidth(2 * separation)
    context.setLineJoin(.round)
    context.addPath(front.path)
    context.strokePath()
    context.endTransparencyLayer()

    // The figure in front, lit from above with a faint shadow onto the plate.
    context.saveGState()
    context.setShadow(offset: CGSize(width: 0, height: -6), blur: 18, color: color(0x000000, alpha: 0.30))
    context.beginTransparencyLayer(auxiliaryInfo: nil)
    fillGradient(front.path, frontColors, in: context, top: front.headY + Bust.head, bottom: plateBottom)
    context.endTransparencyLayer()
    context.restoreGState()

    // A hairline of light along the plate's upper rim.
    context.setStrokeColor(color(0xFFFFFF, alpha: 0.10))
    context.setLineWidth(6)
    context.addPath(plate)
    context.strokePath()
    context.restoreGState()
}

func render(pixels: Int) -> CGImage {
    guard let context = CGContext(
        data: nil, width: pixels, height: pixels,
        bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
    else { fatalError("could not create a \(pixels)x\(pixels) bitmap") }
    let scale = CGFloat(pixels) / canvas
    context.scaleBy(x: scale, y: scale)
    context.setAllowsAntialiasing(true)
    draw(into: context)
    guard let image = context.makeImage() else { fatalError("could not render \(pixels)x\(pixels)") }
    return image
}

func write(_ image: CGImage, to url: URL) {
    guard let destination = CGImageDestinationCreateWithURL(
        url as CFURL, UTType.png.identifier as CFString, 1, nil)
    else { fatalError("could not write \(url.path)") }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { fatalError("could not write \(url.path)") }
}

// MARK: - Asset catalog

/// Every slot a macOS AppIcon set has: point size, then scale.
let slots: [(points: Int, scale: Int)] = [
    (16, 1), (16, 2), (32, 1), (32, 2), (128, 1),
    (128, 2), (256, 1), (256, 2), (512, 1), (512, 2)
]

let output = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .appendingPathComponent("App/Assets.xcassets/AppIcon.appiconset")
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

// One image per distinct pixel size; 16@2x and 32@1x are the same 32px file.
var images: [Int: String] = [:]
var entries: [String] = []
for slot in slots {
    let pixels = slot.points * slot.scale
    let name = images[pixels] ?? "icon_\(pixels).png"
    if images[pixels] == nil {
        images[pixels] = name
        write(render(pixels: pixels), to: output.appendingPathComponent(name))
    }
    entries.append("""
        {
          "filename" : "\(name)",
          "idiom" : "mac",
          "scale" : "\(slot.scale)x",
          "size" : "\(slot.points)x\(slot.points)"
        }
    """)
}

let contents = """
{
  "images" : [
\(entries.joined(separator: ",\n"))
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}

"""
try contents.write(to: output.appendingPathComponent("Contents.json"), atomically: true, encoding: .utf8)
print("wrote \(images.count) PNGs and Contents.json to \(output.path)")

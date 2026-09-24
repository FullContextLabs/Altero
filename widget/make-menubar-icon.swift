#!/usr/bin/env swift
// Draws Altero's menu bar template icon and writes it into the Python
// package's asset dir.
//
//   swift widget/make-menubar-icon.swift [output directory]
//
// Default output is src/altero/assets. Writes menubar-template.png (18x18,
// @1x) and menubar-template@2x.png (36x36, @2x) -- rumps hands both to
// AppKit as a template image, letting macOS recolor it for the light/dark
// menu bar and pick the @2x file on Retina displays. The PNGs are committed;
// this script is how they are regenerated, not a build step.
//
// Same construction as make-app-icon.swift's "another you" mark: a bust
// (circular head, rounded-shoulder body) repeated once, the second standing
// just behind and up-and-right of the first -- the account that takes over.
// The front bust's outline is cut out of the one behind so the two figures
// read apart with no color to do it, which matters at 18px: without a clear
// gap the two shapes merge into one blob. The constants are tuned fresh for
// a small square glyph (rumps resizes whatever it's given to a 20x20pt
// square, so a non-square source would come out stretched) rather than
// scaled down from the app icon's 1024pt canvas.

import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

// MARK: - Geometry

let canvas: CGFloat = 200  // design units; square

struct Bust {
    var headX: CGFloat
    var headY: CGFloat  // the head's centre

    static let head: CGFloat = 34          // radius
    static let neck: CGFloat = 8           // gap between head and shoulders
    static let shoulderWidth: CGFloat = 120
    static let shoulderRise: CGFloat = 46  // shoulder top above the curve's base

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
let front = Bust(headX: 72, headY: 118)
let behind = Bust(headX: 124, headY: 144)
/// The gap cut around the front figure, so the two read as two even at 18px,
/// where there's no color to tell them apart.
let separation: CGFloat = 16

// MARK: - Drawing

func draw(into context: CGContext) {
    let black = CGColor(red: 0, green: 0, blue: 0, alpha: 1)

    // The figure behind, with the front figure's outline cut out of it. The
    // cut happens inside a transparency layer, so it clears only this figure
    // and the canvas stays transparent through it.
    context.beginTransparencyLayer(auxiliaryInfo: nil)
    context.setFillColor(black)
    context.addPath(behind.path)
    context.fillPath()
    context.setBlendMode(.clear)
    context.addPath(front.path)
    context.fillPath()
    context.setLineWidth(2 * separation)
    context.setLineJoin(.round)
    context.addPath(front.path)
    context.strokePath()
    context.endTransparencyLayer()

    // The figure in front, solid on top.
    context.setBlendMode(.normal)
    context.setFillColor(black)
    context.addPath(front.path)
    context.fillPath()
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

// MARK: - Output

let output = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("src/altero/assets")
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

write(render(pixels: 18), to: output.appendingPathComponent("menubar-template.png"))
write(render(pixels: 36), to: output.appendingPathComponent("menubar-template@2x.png"))
print("wrote menubar-template.png and menubar-template@2x.png to \(output.path)")

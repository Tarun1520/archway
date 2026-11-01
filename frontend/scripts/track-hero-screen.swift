// track-hero-screen.swift
//
// Finds where the laptop's dark screen is in EVERY frame of the hero video,
// and prints the result as a ready-made TypeScript file.
//
// WHY
//   When the page scrolls and the camera closes in on the laptop, the real
//   page is drawn on top of the laptop's screen. For it to sit still on the
//   screen instead of wobbling, the page needs to know exactly where the
//   screen is in each frame. This script measures that once.
//
// RUN (from the frontend folder; macOS only, no install needed)
//   swift scripts/track-hero-screen.swift public/hero/hero-scrub.mp4 > src/content/heroScreenTrack.ts
//
// HOW IT WORKS, in four steps
//   1. MEASURE. In each frame, start in the middle of the picture (which is
//      always inside the screen) and walk outward in each direction until the
//      pixels stop being "screen coloured" (dark, and not green like forest).
//      This is done along many lines, not one, and the middle value is kept,
//      so one odd line cannot throw the answer off.
//   2. SHARPEN. A pixel is a small square, so "the edge is at pixel 483" is
//      only accurate to one pixel, and that rounding makes a small picture
//      jitter. The script looks at how bright the two pixels either side of
//      the edge are, and works out where between them the edge really falls.
//   3. SMOOTH. The camera moves smoothly, so the edges must too. Each
//      measurement is averaged with its neighbours in time, which removes
//      what little frame-to-frame noise is left.
//   4. CONTINUE. Near the end the screen is bigger than the picture and its
//      edges cannot be seen any more. From there the script carries on the
//      growth it measured during the last second in which they could.

import AVFoundation
import Foundation

func note(_ text: String) {
  FileHandle.standardError.write((text + "\n").data(using: .utf8)!)
}

guard CommandLine.arguments.count >= 2 else {
  note("usage: swift scripts/track-hero-screen.swift <video> > src/content/heroScreenTrack.ts")
  exit(1)
}

let asset = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
guard let videoTrack = asset.tracks(withMediaType: .video).first else {
  note("No video track found.")
  exit(1)
}
let reader = try AVAssetReader(asset: asset)
let readerOutput = AVAssetReaderTrackOutput(
  track: videoTrack,
  outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
reader.add(readerOutput)
reader.startReading()

/// Pixels brighter than this are outside the laptop's lid.
let outsideBrightness = 62.0
/// Inside the lid, pixels darker than this are the black frame around the
/// display; brighter ones are the lit display. (In this kind of clip the
/// frame measures about 20 and the display about 45, so this sits between.)
let displayBrightness = 34.0

func median(_ values: [Double]) -> Double? {
  if values.isEmpty { return nil }
  let sorted = values.sorted()
  return sorted[sorted.count / 2]
}

/// One frame's measurement, in pixels. `nil` means that edge is outside the picture.
struct Edges {
  var left: Double?, top: Double?, right: Double?, bottom: Double?
}

var times: [Double] = []
var measured: [Edges] = []
var frameWidth = 0, frameHeight = 0
/// How far the lit display is inset from the lid's edge, as a share of the lid's size: left, top, right, bottom.
var insetSamples: [[Double]] = [[], [], [], []]

// ---------------------------------------------------------------------------
// Step 1 and 2: measure every frame, to a fraction of a pixel
// ---------------------------------------------------------------------------
while let sample = readerOutput.copyNextSampleBuffer() {
  guard let buffer = CMSampleBufferGetImageBuffer(sample) else { continue }
  CVPixelBufferLockBaseAddress(buffer, .readOnly)
  defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }

  let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
  let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
  let base = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
  frameWidth = width
  frameHeight = height

  func brightness(_ x: Int, _ y: Int) -> Double {
    let i = y * rowBytes + x * 4 // stored as blue, green, red, alpha
    return (Double(base[i]) + Double(base[i + 1]) + Double(base[i + 2])) / 3
  }
  /// True if the pixel looks like the laptop's screen or the black frame around it.
  func isLid(_ x: Int, _ y: Int) -> Bool {
    let i = y * rowBytes + x * 4
    let b = Int(base[i]), g = Int(base[i + 1]), r = Int(base[i + 2])
    // Dark, and not greener than it is blue (that would be forest shadow).
    return Double(r + g + b) / 3 < outsideBrightness && b >= g - 3 && b >= r - 3
  }

  /// Walks from a starting pixel in one direction until it leaves the lid.
  /// Returns where the edge is, to a fraction of a pixel, or nil if the walk
  /// reached the border of the picture (the edge is out of view).
  func edge(fromX startX: Int, fromY startY: Int, stepX: Int, stepY: Int) -> Double? {
    var x = startX, y = startY
    while true {
      let nextX = x + stepX, nextY = y + stepY
      if nextX < 0 || nextY < 0 || nextX >= width || nextY >= height { return nil }
      if !isLid(nextX, nextY) { break }
      x = nextX
      y = nextY
    }
    let outsideX = x + stepX, outsideY = y + stepY
    if outsideX < 2 || outsideY < 2 || outsideX >= width - 2 || outsideY >= height - 2 { return nil }

    // Sharpen: how far from the last lid pixel toward the first outside pixel
    // does the brightness cross the threshold? (0.5 if it cannot be told.)
    let inside = brightness(x, y), outside = brightness(outsideX, outsideY)
    var share = 0.5
    if outside > outsideBrightness && inside < outsideBrightness {
      share = (outsideBrightness - inside) / (outside - inside)
    }
    let position = Double(stepX != 0 ? x : y) + 0.5 // the centre of the last lid pixel
    return position + Double(stepX + stepY) * share
  }

  /// From just inside the lid's edge, walks inward across the black frame
  /// until it reaches the lit display. Returns where the display begins, to
  /// a fraction of a pixel, or nil if no display was found within `limit` steps.
  func displayEdge(fromX startX: Int, fromY startY: Int, stepX: Int, stepY: Int, limit: Int) -> Double? {
    var x = startX, y = startY, walked = 0
    while brightness(x, y) < displayBrightness {
      x += stepX
      y += stepY
      walked += 1
      if walked > limit || x < 1 || y < 1 || x >= width - 1 || y >= height - 1 { return nil }
    }
    if walked == 0 { return nil }
    let frame = brightness(x - stepX, y - stepY), display = brightness(x, y)
    let share = display > frame ? (displayBrightness - frame) / (display - frame) : 0.5
    let lastFramePixel = Double(stepX != 0 ? x - stepX : y - stepY) + 0.5
    return lastFramePixel + Double(stepX + stepY) * share
  }

  // A rough first look: the tallest dark run down the middle column, then how
  // far it reaches along the row through its middle.
  let middleX = width / 2
  var roughTop = 0, roughLength = 0, runStart = -1
  for y in 0...height {
    let inside = y < height && isLid(middleX, y)
    if inside && runStart < 0 { runStart = y }
    if !inside && runStart >= 0 {
      if y - runStart > roughLength { roughLength = y - runStart; roughTop = runStart }
      runStart = -1
    }
  }
  let roughBottom = roughTop + roughLength
  let middleY = min(max((roughTop + roughBottom) / 2, 0), height - 1)
  var roughLeft = middleX, roughRight = middleX
  while roughLeft > 0 && isLid(roughLeft - 1, middleY) { roughLeft -= 1 }
  while roughRight < width - 1 && isLid(roughRight + 1, middleY) { roughRight += 1 }
  let roughWidth = roughRight - roughLeft + 1

  // The careful measurement: many lines through the middle 40% of the lid
  // (away from its rounded corners), keeping the middle value of each set.
  var lefts: [Double] = [], rights: [Double] = [], tops: [Double] = [], bottoms: [Double] = []
  var leftOut = 0, rightOut = 0, topOut = 0, bottomOut = 0
  // How thick the black frame is on each side, in pixels, one value per line.
  var frameLeft: [Double] = [], frameRight: [Double] = [], frameTop: [Double] = [], frameBottom: [Double] = []
  let frameLimit = max(roughWidth / 5, 4)
  let rowStep = max(1, roughLength * 2 / 5 / 14), columnStep = max(1, roughWidth * 2 / 5 / 14)

  var y = roughTop + roughLength * 3 / 10
  while y <= roughTop + roughLength * 7 / 10 && y < height {
    if isLid(middleX, y) {
      if let value = edge(fromX: middleX, fromY: y, stepX: -1, stepY: 0) {
        lefts.append(value)
        if let display = displayEdge(fromX: Int(value) + 1, fromY: y, stepX: 1, stepY: 0, limit: frameLimit) {
          frameLeft.append(display - value)
        }
      } else {
        leftOut += 1
      }
      if let value = edge(fromX: middleX, fromY: y, stepX: 1, stepY: 0) {
        rights.append(value)
        if let display = displayEdge(fromX: Int(value) - 1, fromY: y, stepX: -1, stepY: 0, limit: frameLimit) {
          frameRight.append(value - display)
        }
      } else {
        rightOut += 1
      }
    }
    y += rowStep
  }
  var x = roughLeft + roughWidth * 3 / 10
  while x <= roughLeft + roughWidth * 7 / 10 && x < width {
    if isLid(x, middleY) {
      // The webcam sits in the middle of the top frame and would confuse the
      // thickness measurement, so the few lines nearest the middle skip it.
      let nearWebcam = abs(x - middleX) < roughWidth / 12
      if let value = edge(fromX: x, fromY: middleY, stepX: 0, stepY: -1) {
        tops.append(value)
        if !nearWebcam, let display = displayEdge(fromX: x, fromY: Int(value) + 1, stepX: 0, stepY: 1, limit: frameLimit) {
          frameTop.append(display - value)
        }
      } else {
        topOut += 1
      }
      if let value = edge(fromX: x, fromY: middleY, stepX: 0, stepY: 1) {
        bottoms.append(value)
        if let display = displayEdge(fromX: x, fromY: Int(value) - 1, stepX: 0, stepY: -1, limit: frameLimit) {
          frameBottom.append(value - display)
        }
      } else {
        bottomOut += 1
      }
    }
    x += columnStep
  }

  // An edge counts as "out of view" if most of its lines ran off the picture.
  var edges = Edges()
  edges.left = leftOut > lefts.count ? nil : median(lefts)
  edges.right = rightOut > rights.count ? nil : median(rights)
  edges.top = topOut > tops.count ? nil : median(tops)
  edges.bottom = bottomOut > bottoms.count ? nil : median(bottoms)

  // While the lid is a good size and fully in view, record how thick the
  // black frame is on each side, as a share of the lid's size.
  if let left = edges.left, let right = edges.right, let top = edges.top, let bottom = edges.bottom {
    let lidWidth = right - left, lidHeight = bottom - top
    if lidWidth > 260 && lidWidth < 900 {
      if let value = median(frameLeft) { insetSamples[0].append(value / lidWidth) }
      if let value = median(frameTop) { insetSamples[1].append(value / lidHeight) }
      if let value = median(frameRight) { insetSamples[2].append(value / lidWidth) }
      if let value = median(frameBottom) { insetSamples[3].append(value / lidHeight) }
    }
  }

  times.append(CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample)))
  measured.append(edges)
}

let count = times.count
guard count > 30 else {
  note("Too few frames were read.")
  exit(1)
}
let framesPerSecond = Double(count - 1) / (times[count - 1] - times[0])
let oneSecond = Int(framesPerSecond.rounded())

// The measurements are usable up to the first frame where an edge goes out of view.
let sidesEnd = measured.firstIndex { $0.left == nil || $0.right == nil } ?? count
let topBottomEnd = min(measured.firstIndex { $0.top == nil || $0.bottom == nil } ?? count, sidesEnd)
guard topBottomEnd > oneSecond * 2 else {
  note("The laptop screen could not be followed for long enough. Is its screen dark, and in the middle of the picture?")
  exit(1)
}

// ---------------------------------------------------------------------------
// Step 3: smooth each edge over time
// ---------------------------------------------------------------------------
/// Averages each value with its neighbours, nearer ones counting for more.
func smooth(_ values: [Double]) -> [Double] {
  let weights = [0.06, 0.24, 0.40, 0.24, 0.06]
  return values.indices.map { index in
    var total = 0.0, weightTotal = 0.0
    for (offset, weight) in weights.enumerated() {
      let neighbour = index + offset - 2
      if neighbour >= 0 && neighbour < values.count {
        total += values[neighbour] * weight
        weightTotal += weight
      }
    }
    return total / weightTotal
  }
}

var left = smooth((0..<sidesEnd).map { measured[$0].left! })
var right = smooth((0..<sidesEnd).map { measured[$0].right! })
var top = smooth((0..<topBottomEnd).map { measured[$0].top! })
var bottom = smooth((0..<topBottomEnd).map { measured[$0].bottom! })

// ---------------------------------------------------------------------------
// Step 4: carry on once the edges have left the picture
// ---------------------------------------------------------------------------
/// The steady rate of change of `values` over time (the slope of the best-fit line).
func slope(_ sampleTimes: [Double], _ values: [Double]) -> Double {
  let n = Double(values.count)
  let meanTime = sampleTimes.reduce(0, +) / n, meanValue = values.reduce(0, +) / n
  var top = 0.0, bottom = 0.0
  for i in values.indices {
    top += (sampleTimes[i] - meanTime) * (values[i] - meanValue)
    bottom += (sampleTimes[i] - meanTime) * (sampleTimes[i] - meanTime)
  }
  return bottom == 0 ? 0 : top / bottom
}

// 4a. Top and bottom go out of view first. Keep the lid's shape (height for a
//     given width) and its vertical drift from the last second they were seen.
let lastSeen = topBottomEnd - 1
let recent = (topBottomEnd - oneSecond)..<topBottomEnd
let recentTimes = recent.map { times[$0] }
let shape = (bottom[lastSeen] - top[lastSeen]) / (right[lastSeen] - left[lastSeen])
let middleDrift = slope(recentTimes, recent.map { (top[$0] + bottom[$0]) / 2 })
let lastMiddleY = (top[lastSeen] + bottom[lastSeen]) / 2

// 4b. Then the sides go too. Keep growing the width at the rate it was
//     growing (a steady percentage per second), drifting sideways as before.
let sidesLast = sidesEnd - 1
let sidesRecent = (sidesEnd - oneSecond)..<sidesEnd
let sidesTimes = sidesRecent.map { times[$0] }
let growth = slope(sidesTimes, sidesRecent.map { log(right[$0] - left[$0]) })
let sideDrift = slope(sidesTimes, sidesRecent.map { (left[$0] + right[$0]) / 2 })
let lastWidth = right[sidesLast] - left[sidesLast]
let lastMiddleX = (left[sidesLast] + right[sidesLast]) / 2

for index in sidesEnd..<count {
  let elapsed = times[index] - times[sidesLast]
  let lidWidth = lastWidth * exp(growth * elapsed)
  let middle = lastMiddleX + sideDrift * elapsed
  left.append(middle - lidWidth / 2)
  right.append(middle + lidWidth / 2)
}
for index in topBottomEnd..<count {
  let lidHeight = (right[index] - left[index]) * shape
  let middle = lastMiddleY + middleDrift * (times[index] - times[lastSeen])
  top.append(middle - lidHeight / 2)
  bottom.append(middle + lidHeight / 2)
}

// ---------------------------------------------------------------------------
// Print the TypeScript file
// ---------------------------------------------------------------------------
let insets = insetSamples.map { median($0) ?? 0.03 }
func number(_ value: Double) -> String { String(format: "%.5f", value) }

print("""
/**
 * Where the laptop's lid is in each frame of the hero clip.
 *
 * GENERATED FILE. Do not edit the numbers by hand. To make it again (for
 * example after changing the clip), run from the frontend folder:
 *
 *   swift scripts/track-hero-screen.swift public/hero/hero-scrub.mp4 > src/content/heroScreenTrack.ts
 *
 * As the camera closes in on the laptop, the real page is drawn on top of the
 * laptop's screen and grows with it. For that, the page has to know where the
 * screen is in every frame. These numbers are that knowledge, and they belong
 * to one specific clip.
 *
 * Each row: [time in seconds, left, top, right, bottom].
 * The four edges are fractions of the video frame: 0 is the frame's left or
 * top edge, 1 is its right or bottom edge. Values below 0 or above 1 mean the
 * edge has moved outside the frame (the screen is bigger than the picture).
 *
 * Rows up to \(String(format: "%.2f", times[topBottomEnd - 1])) s were measured. After that the lid's edges leave the
 * frame, so the rows continue the growth measured just before.
 */

/** [time, left, top, right, bottom] */
export type ScreenKeyframe = readonly [number, number, number, number, number]

/** How many frames the clip shows per second. The page moves in step with them. */
export const heroClipFramesPerSecond = \(String(format: "%.3f", framesPerSecond))

/**
 * The rows above describe the laptop's whole lid, including the black frame
 * around the display. These say how much to trim from each side to get the
 * lit display itself, as fractions of the lid's width or height. Measured
 * from the clip.
 */
export const displayInsets = { left: \(number(insets[0])), top: \(number(insets[1])), right: \(number(insets[2])), bottom: \(number(insets[3])) }

export const heroScreenTrack: readonly ScreenKeyframe[] = [
""")
for index in 0..<count {
  let w = Double(frameWidth), h = Double(frameHeight)
  print("  [\(String(format: "%.4f", times[index])), \(number(left[index] / w)), \(number(top[index] / h)), \(number(right[index] / w)), \(number(bottom[index] / h))],")
}
print("]")

note("Frames: \(count) at \(String(format: "%.2f", framesPerSecond)) per second. Measured up to \(String(format: "%.2f", times[topBottomEnd - 1])) s (top/bottom) and \(String(format: "%.2f", times[sidesEnd - 1])) s (sides).")
note("Display insets (left, top, right, bottom): \(insets.map(number).joined(separator: ", "))")

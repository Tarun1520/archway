// prepare-hero-video.swift
//
// Gets a hero video ready for scroll scrubbing.
//
// WHY
//   A normal video file stores a complete picture ("keyframe") only every
//   second or two. The frames in between are stored as "what changed since
//   the last frame". That is fine for playing forward, but the hero jumps to
//   arbitrary moments as the page scrolls, including backward. To show a
//   frame that is not a keyframe, the browser must rebuild it from the last
//   keyframe, which makes scrolling stutter.
//
//   This script re-saves the clip with EVERY frame as a keyframe, so any
//   moment can be shown instantly. The file gets bigger; that is the trade.
//   It also drops the sound (the hero is silent) and saves the first frame
//   as a still image to show while the video loads.
//
// RUN (from the frontend folder; macOS only, no install needed)
//   swift scripts/prepare-hero-video.swift <your-clip.mp4>
//
//   Optional: lift off a small see-through logo that sits in the same place
//   in every frame. Give the box that contains it, in the clip's own pixels
//   (left,top,width,height):
//   swift scripts/prepare-hero-video.swift <your-clip.mp4> --erase-mark 1118,558,84,84
//
//   Optional: enlarge the picture, for example to twice its size:
//   swift scripts/prepare-hero-video.swift <your-clip.mp4> --upscale 2
//   (Both options can be used together.)
//
//   Optional: give the result a different file name, to keep more than one
//   size of the same clip. This is how the two sizes the site uses were made:
//   swift scripts/prepare-hero-video.swift clip.mp4 --erase-mark 1118,558,84,84 --upscale 2
//   swift scripts/prepare-hero-video.swift clip.mp4 --erase-mark 1118,558,84,84 --name hero-scrub-720
//
// WRITES
//   public/hero/hero-scrub.mp4     the scrubbing-ready video (or the name given with --name)
//   public/hero/hero-poster.jpg    its first frame (only when no --name is given)
//
// It never changes the clip you give it.
//
// ABOUT ENLARGING
//   Enlarging cannot add detail that was never filmed. A 1280 x 720 clip made
//   twice the size has four times the pixels, but they are worked out from
//   the same picture. What it does give is a cleaner, slightly crisper
//   enlargement than the browser would make on the fly when it stretches a
//   small clip over a large window: the script uses a high-quality method
//   ("Lanczos") and then sharpens edges a little. For real extra detail, the
//   clip has to be generated or filmed at the higher resolution.
//
// HOW THE LOGO IS LIFTED OFF
//   A see-through white logo changes each pixel under it like this:
//       seen = (1 - a) x real  +  a x white
//   where `a` is how solid the logo is at that pixel (0 = not there).
//   Turn that around and the real pixel comes back:
//       real = (seen - a x white) / (1 - a)
//   To learn `a` for every pixel, the script looks at the clip's last frames.
//   They must be a flat, dark color under the logo there (this clip ends
//   inside the laptop's dark screen), so anything brighter than the
//   surroundings can only be the logo. Because the picture underneath is
//   recovered rather than painted over, texture such as grass survives.
//   This only affects what is visible in the picture.

import AVFoundation
import CoreGraphics
import CoreImage
import Foundation
import ImageIO

// --- Read the command line ---------------------------------------------------
let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
  print("usage: swift scripts/prepare-hero-video.swift <source video> [--erase-mark left,top,width,height] [--upscale factor]")
  exit(1)
}

/// How many times larger to make the picture. 1 leaves it as it is.
var upscale = 1.0
if let flag = arguments.firstIndex(of: "--upscale"), arguments.count > flag + 1 {
  guard let factor = Double(arguments[flag + 1]), factor >= 1, factor <= 4 else {
    print("--upscale needs a number from 1 to 4, for example 2")
    exit(1)
  }
  upscale = factor
}

struct Box { let left: Int, top: Int, width: Int, height: Int }
var markBox: Box?
if let flag = arguments.firstIndex(of: "--erase-mark"), arguments.count > flag + 1 {
  let numbers = arguments[flag + 1].split(separator: ",").compactMap { Int($0) }
  guard numbers.count == 4 else {
    print("--erase-mark needs four whole numbers: left,top,width,height")
    exit(1)
  }
  markBox = Box(left: numbers[0], top: numbers[1], width: numbers[2], height: numbers[3])
}

let sourceURL = URL(fileURLWithPath: arguments[1])
let outputFolder = URL(fileURLWithPath: "public/hero")
var outputName = "hero-scrub"
if let flag = arguments.firstIndex(of: "--name"), arguments.count > flag + 1 {
  outputName = arguments[flag + 1]
}
let writesPoster = outputName == "hero-scrub"
let videoURL = outputFolder.appendingPathComponent("\(outputName).mp4")
let posterURL = outputFolder.appendingPathComponent("hero-poster.jpg")

try FileManager.default.createDirectory(at: outputFolder, withIntermediateDirectories: true)
try? FileManager.default.removeItem(at: videoURL)

let asset = AVURLAsset(url: sourceURL)
guard let track = asset.tracks(withMediaType: .video).first else {
  print("No video track found in \(sourceURL.path)")
  exit(1)
}
let size = track.naturalSize
let duration = CMTimeGetSeconds(asset.duration)

// The size of the picture that gets written. Video sizes must be even numbers.
let outputWidth = Int((size.width * upscale / 2).rounded()) * 2
let outputHeight = Int((size.height * upscale / 2).rounded()) * 2

/// Gives exact still frames from a video.
func frameGrabber(for asset: AVAsset) -> AVAssetImageGenerator {
  let grabber = AVAssetImageGenerator(asset: asset)
  grabber.requestedTimeToleranceBefore = .zero
  grabber.requestedTimeToleranceAfter = .zero
  grabber.appliesPreferredTrackTransform = true
  return grabber
}

// --- Step 1 (only with --erase-mark): learn the logo's shape -----------------
// `shape` holds, for each pixel of the box, how much of the logo is there:
// 0 = none, 1 = the logo at its most solid.
var shape: [Double] = []

/// The width of the frame of pixels around the box's edge used to judge the
/// color of the surroundings. The logo must not reach into it.
let rim = 6

func isRim(_ x: Int, _ y: Int, _ box: Box) -> Bool {
  x < rim || y < rim || x >= box.width - rim || y >= box.height - rim
}

if let box = markBox {
  let grabber = frameGrabber(for: asset)
  var solidity = [Double](repeating: 0, count: box.width * box.height)
  let sampleTimes = stride(from: duration - 0.40, through: duration - 0.05, by: 0.07).map { $0 }

  for time in sampleTimes {
    let frame = try grabber.copyCGImage(at: CMTime(seconds: time, preferredTimescale: 600), actualTime: nil)
    guard let crop = frame.cropping(to: CGRect(x: box.left, y: box.top, width: box.width, height: box.height)) else {
      print("The --erase-mark box is outside the picture.")
      exit(1)
    }
    var pixels = [UInt8](repeating: 0, count: box.width * box.height * 4)
    let context = CGContext(
      data: &pixels, width: box.width, height: box.height, bitsPerComponent: 8, bytesPerRow: box.width * 4,
      space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    context.draw(crop, in: CGRect(x: 0, y: 0, width: box.width, height: box.height))

    // The color of the surroundings: the average of the rim.
    var rimTotal = [Double](repeating: 0, count: 3)
    var rimCount = 0.0
    for y in 0..<box.height {
      for x in 0..<box.width where isRim(x, y, box) {
        for channel in 0..<3 { rimTotal[channel] += Double(pixels[(y * box.width + x) * 4 + channel]) }
        rimCount += 1
      }
    }
    let surround = rimTotal.map { $0 / rimCount }
    guard surround.max()! < 90 else {
      print("The last frames are not dark under the logo, so its shape cannot be measured from them.")
      exit(1)
    }

    // How solid the logo must be at each pixel to explain how bright it is.
    for y in 0..<box.height {
      for x in 0..<box.width {
        var total = 0.0
        for channel in 0..<3 {
          let seen = Double(pixels[(y * box.width + x) * 4 + channel])
          total += (seen - surround[channel]) / (255 - surround[channel])
        }
        solidity[y * box.width + x] += total / 3 / Double(sampleTimes.count)
      }
    }
  }

  // Scale so the logo's solid middle is 1, and ignore faint noise.
  let peak = solidity.sorted()[Int(Double(solidity.count) * 0.97)]
  guard peak > 0.08 else {
    print("No logo found in the --erase-mark box.")
    exit(1)
  }
  shape = solidity.enumerated().map { index, value in
    let x = index % box.width, y = index / box.width
    if isRim(x, y, box) || value < peak * 0.08 { return 0 }
    return min(value / peak, 1.15)
  }
  print(String(format: "Logo found: about %.0f%% solid at its middle.", peak * 100))
}

// --- Step 2: read every frame, fix it if asked, write it back ----------------
let reader = try AVAssetReader(asset: asset)
let readerOutput = AVAssetReaderTrackOutput(
  track: track,
  outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
reader.add(readerOutput)

let writer = try AVAssetWriter(outputURL: videoURL, fileType: .mp4)
writer.shouldOptimizeForNetworkUse = true // puts the index at the start, so the browser can begin at once

let writerInput = AVAssetWriterInput(
  mediaType: .video,
  outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: outputWidth,
    AVVideoHeightKey: outputHeight,
    AVVideoCompressionPropertiesKey: [
      AVVideoMaxKeyFrameIntervalKey: 1, // the whole point: a keyframe on every frame
      AVVideoAllowFrameReorderingKey: false,
      // High, so the re-save loses no visible detail. A bigger picture needs more.
      AVVideoAverageBitRateKey: Int(12_000_000 * Double(outputWidth * outputHeight) / Double(size.width * size.height) * (upscale > 1 ? 0.75 : 1)),
      AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
  ])
writerInput.expectsMediaDataInRealTime = false
let frameWriter = AVAssetWriterInputPixelBufferAdaptor(
  assetWriterInput: writerInput,
  sourcePixelBufferAttributes: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
    kCVPixelBufferWidthKey as String: outputWidth,
    kCVPixelBufferHeightKey as String: outputHeight,
  ])
writer.add(writerInput)

reader.startReading()
writer.startWriting()
writer.startSession(atSourceTime: .zero)

/// Lifts the logo off one frame, in place. `strength` is how solid the logo
/// was in the previous frame; the new value is returned for the next one.
func eraseMark(in buffer: CVPixelBuffer, box: Box, previousStrength: Double?) -> Double {
  CVPixelBufferLockBaseAddress(buffer, [])
  defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
  let base = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
  let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
  func offset(_ x: Int, _ y: Int) -> Int { (box.top + y) * rowBytes + (box.left + x) * 4 }

  // The color of the surroundings in THIS frame.
  var rimTotal = [Double](repeating: 0, count: 3)
  var rimCount = 0.0
  for y in 0..<box.height {
    for x in 0..<box.width where isRim(x, y, box) {
      for channel in 0..<3 { rimTotal[channel] += Double(base[offset(x, y) + channel]) }
      rimCount += 1
    }
  }
  let surround = rimTotal.map { $0 / rimCount }

  // How solid the logo is in this frame: the value that best explains how
  // much brighter the logo's area is than its surroundings. It varies a
  // little from frame to frame, so it is measured each time, kept within a
  // sensible range, and smoothed against the previous frame.
  var explained = 0.0, possible = 0.0
  for y in 0..<box.height {
    for x in 0..<box.width {
      let amount = shape[y * box.width + x]
      if amount == 0 { continue }
      for channel in 0..<3 {
        let headroom = 255 - surround[channel]
        explained += amount * headroom * (Double(base[offset(x, y) + channel]) - surround[channel])
        possible += amount * headroom * amount * headroom
      }
    }
  }
  var strength = possible > 0 ? explained / possible : 0.28
  strength = min(max(strength, 0.24), 0.32)
  if let previous = previousStrength { strength = previous * 0.6 + strength * 0.4 }

  // real = (seen - a x white) / (1 - a), for every pixel the logo touches.
  for y in 0..<box.height {
    for x in 0..<box.width {
      let a = shape[y * box.width + x] * strength
      if a == 0 { continue }
      for channel in 0..<3 {
        let seen = Double(base[offset(x, y) + channel])
        let real = (seen - a * 255) / (1 - a)
        base[offset(x, y) + channel] = UInt8(min(max(real, 0), 255).rounded())
      }
    }
  }

  // The logo's soft outline is the hardest part to recover exactly, and can
  // leave a hairline trace. Each pixel on the outline is replaced by the
  // average of itself and its eight neighbours, which blends the trace away.
  var recovered = [UInt8](repeating: 0, count: box.width * box.height * 3)
  for y in 0..<box.height {
    for x in 0..<box.width {
      for channel in 0..<3 { recovered[(y * box.width + x) * 3 + channel] = base[offset(x, y) + channel] }
    }
  }
  for y in 1..<(box.height - 1) {
    for x in 1..<(box.width - 1) {
      let amount = shape[y * box.width + x]
      let onOutline = amount > 0 && amount < 0.9
      if !onOutline { continue }
      for channel in 0..<3 {
        var total = 0
        for dy in -1...1 {
          for dx in -1...1 { total += Int(recovered[((y + dy) * box.width + (x + dx)) * 3 + channel]) }
        }
        base[offset(x, y) + channel] = UInt8(total / 9)
      }
    }
  }
  return strength
}

/// Core Image does the enlarging on the graphics card.
let imageWorker = CIContext()

/// Returns a larger copy of one frame: enlarged with the Lanczos method, then
/// sharpened a little so edges softened by the enlarging become crisp again.
func enlarge(_ picture: CVPixelBuffer) -> CVPixelBuffer? {
  var larger: CVPixelBuffer?
  CVPixelBufferPoolCreatePixelBuffer(nil, frameWriter.pixelBufferPool!, &larger)
  guard let output = larger else { return nil }

  let source = CIImage(cvPixelBuffer: picture)
  let scaled = source.applyingFilter(
    "CILanczosScaleTransform",
    parameters: [kCIInputScaleKey: Double(outputHeight) / Double(size.height), kCIInputAspectRatioKey: 1.0])
  let sharpened = scaled.applyingFilter(
    "CIUnsharpMask",
    parameters: [kCIInputRadiusKey: 1.6, kCIInputIntensityKey: 0.45])

  let wholeFrame = CGRect(x: 0, y: 0, width: outputWidth, height: outputHeight)
  imageWorker.render(sharpened.cropped(to: wholeFrame), to: output, bounds: wholeFrame, colorSpace: CGColorSpace(name: CGColorSpace.itur_709))
  return output
}

var frameCount = 0
var strength: Double?
while let sample = readerOutput.copyNextSampleBuffer() {
  guard let picture = CMSampleBufferGetImageBuffer(sample) else { continue }
  if let box = markBox {
    strength = eraseMark(in: picture, box: box, previousStrength: strength)
  }
  while !writerInput.isReadyForMoreMediaData { usleep(2000) }

  let time = CMSampleBufferGetPresentationTimeStamp(sample)
  if upscale > 1, let larger = enlarge(picture) {
    frameWriter.append(larger, withPresentationTime: time)
  } else {
    frameWriter.append(picture, withPresentationTime: time)
  }
  frameCount += 1
}
writerInput.markAsFinished()

let finished = DispatchSemaphore(value: 0)
writer.finishWriting { finished.signal() }
finished.wait()

guard writer.status == .completed else {
  print("Writing failed: \(writer.error?.localizedDescription ?? "unknown error")")
  exit(1)
}

// --- Step 3: save the first frame of the result as the poster image ----------
let firstFrame = try frameGrabber(for: AVURLAsset(url: videoURL)).copyCGImage(at: .zero, actualTime: nil)
if writesPoster, let destination = CGImageDestinationCreateWithURL(posterURL as CFURL, "public.jpeg" as CFString, 1, nil) {
  CGImageDestinationAddImage(destination, firstFrame, [kCGImageDestinationLossyCompressionQuality: 0.86] as CFDictionary)
  CGImageDestinationFinalize(destination)
}

let megabytes = Double((try? FileManager.default.attributesOfItem(atPath: videoURL.path)[.size] as? Int) ?? 0) / 1_000_000
print(String(format: "Done: %d frames, %d x %d, %.1f seconds, %.1f MB", frameCount, outputWidth, outputHeight, duration, megabytes))
print("Wrote \(videoURL.path)" + (writesPoster ? " and \(posterURL.path)" : ""))

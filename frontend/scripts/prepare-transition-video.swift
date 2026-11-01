// prepare-transition-video.swift
//
// Gets the "space transition" clip ready to play between the welcome page and
// the workspace: lifts off the corner logo, enlarges it to 1080p, and keeps
// the sound with a soft fade at the start and the end.
//
// RUN (from the frontend folder; macOS only, no install needed)
//   swift scripts/prepare-transition-video.swift <clip.mp4> --erase-mark 1118,558,84,84
//
//   Options (all optional):
//     --erase-mark left,top,width,height   the box around a see-through logo, in the clip's own pixels
//     --size 1920x1080                     the picture size to write (default 1920x1080; 2560x1440 for 2K)
//     --bitrate-mbps 14                    the video quality (default: about 8 per 1080p of picture, so 14 for 2K)
//     --fade-in 0.6                        seconds for the sound to rise at the start (default 0.6)
//     --fade-out 1.6                       seconds for the sound to die away at the end (default 1.6)
//     --name space-transition              the file name to write (default space-transition)
//     --still-mark-fades-by 2.6            the clip opens on a still picture that ALREADY had the
//                                          logo, and that picture has faded away by this many seconds
//
// WRITES
//   public/transition/<name>.mp4
// It never changes the clip you give it.
//
// HOW IT DIFFERS FROM prepare-hero-video.swift
//   The hero is scrubbed by scroll, so it needs a keyframe on every frame and
//   no sound. This clip simply plays forward, so it keeps normal keyframes (a
//   much smaller file) and keeps its sound.
//
//   The logo is lifted off the same way, by recovering the picture under it:
//       seen = (1 - a) x real  +  a x white     so     real = (seen - a x white) / (1 - a)
//   where `a` is how solid the logo is at each pixel. The hero script learns
//   `a` from the clip's last frames, which are dark there. This clip ends
//   bright, so instead `a` is learned from EVERY frame in which the logo sits
//   on something dark and even, wherever in the clip that is. For each pixel
//   the script keeps a low value (the 25th percentile) across those frames, so
//   a star or a streak that happens to pass under the logo for a while is not
//   mistaken for part of it: the logo is there in every frame, a star is not.
//   The logo is a little more or less solid from frame to frame. Measuring
//   that per frame was tried and dropped: stars and streaks crossing the logo
//   made the measurement jump about, and a correction that jumps flickers.
//   One steady correction for the whole clip looks cleaner in motion.
//
// A SECOND COPY OF THE LOGO (--still-mark-fades-by)
//   A clip can open on a still picture that Gemini had already marked. While
//   that picture dissolves into the film, its own copy of the logo fades out
//   on top of the film's logo, so for a moment there are two. With this option
//   the script looks at what is left after the normal correction, in that
//   opening stretch only, and learns the second copy's own shape from it (the
//   typical leftover across those frames). It then measures how strong the
//   copy is in each frame, smooths that over neighbouring frames so it cannot flicker, and
//   subtracts it. Frames after the given time are not touched by this step.
//
// ABOUT ENLARGING
//   1280 x 720 to 1920 x 1080 cannot add detail that was never generated. It
//   is a clean, high-quality enlargement (Lanczos, then a light sharpen),
//   better than the browser stretching a small clip over a big window.

import AVFoundation
import CoreGraphics
import CoreImage
import Foundation

// --- Read the command line ---------------------------------------------------
let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
  print("usage: swift scripts/prepare-transition-video.swift <clip.mp4> [--erase-mark l,t,w,h] [--size 1920x1080] [--fade-in s] [--fade-out s] [--name n] [--still-mark-fades-by s]")
  exit(1)
}

func option(_ flag: String) -> String? {
  guard let index = arguments.firstIndex(of: flag), arguments.count > index + 1 else { return nil }
  return arguments[index + 1]
}

struct Box { let left: Int, top: Int, width: Int, height: Int }
var markBox: Box?
if let text = option("--erase-mark") {
  let numbers = text.split(separator: ",").compactMap { Int($0) }
  guard numbers.count == 4 else {
    print("--erase-mark needs four whole numbers: left,top,width,height")
    exit(1)
  }
  markBox = Box(left: numbers[0], top: numbers[1], width: numbers[2], height: numbers[3])
}

let sizeParts = (option("--size") ?? "1920x1080").split(separator: "x").compactMap { Int($0) }
guard sizeParts.count == 2, sizeParts[0] % 2 == 0, sizeParts[1] % 2 == 0 else {
  print("--size needs two even numbers, for example 1920x1080")
  exit(1)
}
let outputWidth = sizeParts[0]
let outputHeight = sizeParts[1]
let fadeIn = Double(option("--fade-in") ?? "0.6") ?? 0.6
let fadeOut = Double(option("--fade-out") ?? "1.6") ?? 1.6
// About 8 Mbit/s for 1080p, and more for bigger pictures so a 2K film keeps its clarity.
// --bitrate-mbps overrides it.
let bitRate = Int((Double(option("--bitrate-mbps") ?? "") ?? (8.0 * Double(outputWidth * outputHeight) / Double(1920 * 1080))) * 1_000_000)
let stillMarkFadesBy = option("--still-mark-fades-by").flatMap(Double.init)

let sourceURL = URL(fileURLWithPath: arguments[1])
let outputFolder = URL(fileURLWithPath: "public/transition")
let videoURL = outputFolder.appendingPathComponent("\(option("--name") ?? "space-transition").mp4")
try FileManager.default.createDirectory(at: outputFolder, withIntermediateDirectories: true)
// The film is written in a temporary folder first and moved into place at the
// end. Writing straight into a synced folder (this project lives in iCloud
// Drive) left half-written ".sb-..." copies behind next to the result.
let workingURL = FileManager.default.temporaryDirectory.appendingPathComponent("transition-\(UUID().uuidString).mp4")

let asset = AVURLAsset(url: sourceURL)
guard let videoTrack = asset.tracks(withMediaType: .video).first else {
  print("No video track found in \(sourceURL.path)")
  exit(1)
}
let audioTrack = asset.tracks(withMediaType: .audio).first
let sourceSize = videoTrack.naturalSize
let duration = CMTimeGetSeconds(asset.duration)

let pixelFormat: [String: Any] = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]

// --- Step 1 (only with --erase-mark): learn how solid the logo is, pixel by pixel ---
/// The width of the frame of pixels around the box's edge used to judge the
/// colour of the surroundings. The logo must not reach into it.
let rim = 6
func isRim(_ x: Int, _ y: Int, _ box: Box) -> Bool {
  x < rim || y < rim || x >= box.width - rim || y >= box.height - rim
}

/// The average colour of the rim, and how uneven it is (0 = perfectly even).
func surroundings(_ base: UnsafePointer<UInt8>, _ rowBytes: Int, _ box: Box) -> (colour: [Double], unevenness: Double) {
  var total = [0.0, 0.0, 0.0], squares = 0.0, count = 0.0
  for y in 0..<box.height {
    for x in 0..<box.width where isRim(x, y, box) {
      let offset = (box.top + y) * rowBytes + (box.left + x) * 4
      var brightness = 0.0
      for channel in 0..<3 {
        let value = Double(base[offset + channel])
        total[channel] += value
        brightness += value / 3
      }
      squares += brightness * brightness
      count += 1
    }
  }
  let colour = total.map { $0 / count }
  let mean = colour.reduce(0, +) / 3
  return (colour, (squares / count - mean * mean).squareRoot())
}

/// For each pixel of the box: how solid the logo is there (0 = not there).
var alpha: [Double] = []
/// For each pixel of the box: whether it is on (or right beside) the logo's soft edge.
var outline: [Bool] = []

if let box = markBox {
  let reader = try AVAssetReader(asset: asset)
  let output = AVAssetReaderTrackOutput(track: videoTrack, outputSettings: pixelFormat)
  reader.add(output)
  reader.startReading()

  var samples = [[Double]](repeating: [], count: box.width * box.height)
  var usedFrames = 0
  while let sample = output.copyNextSampleBuffer() {
    guard let picture = CMSampleBufferGetImageBuffer(sample) else { continue }
    CVPixelBufferLockBaseAddress(picture, .readOnly)
    let base = UnsafePointer(CVPixelBufferGetBaseAddress(picture)!.assumingMemoryBound(to: UInt8.self))
    let rowBytes = CVPixelBufferGetBytesPerRow(picture)
    let around = surroundings(base, rowBytes, box)
    // Only frames where the logo sits on something dark and even can show its shape.
    if around.colour.max()! < 60 && around.unevenness < 14 {
      usedFrames += 1
      for y in 0..<box.height {
        for x in 0..<box.width {
          let offset = (box.top + y) * rowBytes + (box.left + x) * 4
          var total = 0.0
          for channel in 0..<3 {
            total += (Double(base[offset + channel]) - around.colour[channel]) / (255 - around.colour[channel])
          }
          samples[y * box.width + x].append(total / 3)
        }
      }
    }
    CVPixelBufferUnlockBaseAddress(picture, .readOnly)
  }
  guard usedFrames >= 8 else {
    print("Only \(usedFrames) frames are dark under the logo; that is too few to learn its shape.")
    exit(1)
  }

  // A low value across the frames: the logo is in all of them, a passing star is not.
  alpha = samples.enumerated().map { index, values in
    if isRim(index % box.width, index / box.width, box) { return 0 }
    let sorted = values.sorted()
    let value = sorted[Int(Double(sorted.count) * 0.25)]
    return value < 0.03 ? 0 : min(value, 0.9)
  }
  let peak = alpha.max() ?? 0
  guard peak > 0.08 else {
    print("No logo found in the --erase-mark box.")
    exit(1)
  }
  print(String(format: "Logo learned from %d dark frames: about %.0f%% solid at its middle.", usedFrames, peak * 100))

  // The logo's edge: where it is partly solid, widened by one pixel each way.
  let edge = alpha.map { $0 > 0 && $0 < peak * 0.9 }
  outline = (0..<edge.count).map { index in
    let x = index % box.width, y = index / box.width
    for dy in -1...1 {
      for dx in -1...1 {
        let nx = x + dx, ny = y + dy
        if nx >= 0, ny >= 0, nx < box.width, ny < box.height, edge[ny * box.width + nx] { return true }
      }
    }
    return false
  }
}

// --- Step 1b (only with --still-mark-fades-by): learn the second copy ----------
/// The brightness the second copy adds at each pixel, at strength 1 (its middle is about 1).
var stillShape: [Double] = []
/// Its soft edge, widened by a pixel, blended like the first logo's.
var stillOutline: [Bool] = []
/// How strong the second copy is in each frame of the opening stretch, by frame number (in brightness levels).
var stillStrength: [Int: Double] = [:]

/// The box's brightness (average of the three colours) after the steady
/// correction, without changing the frame.
func correctedBrightness(_ base: UnsafePointer<UInt8>, _ rowBytes: Int, _ box: Box) -> [Double] {
  (0..<(box.width * box.height)).map { index in
    let x = index % box.width, y = index / box.width
    let offset = (box.top + y) * rowBytes + (box.left + x) * 4
    let a = alpha[index]
    var total = 0.0
    for channel in 0..<3 { total += (Double(base[offset + channel]) - a * 255) / (1 - a) }
    return total / 3
  }
}

func median(_ values: [Double]) -> Double {
  let sorted = values.sorted()
  return sorted.isEmpty ? 0 : sorted[sorted.count / 2]
}

/// The background behind the box, as a flat surface that may slope (fitted to
/// the rim by least squares: brightness = c + gx * x + gy * y). While a picture
/// dissolves the background is often a gradient across the box, and one
/// average colour would misjudge what is left of the logo.
func slopedBackground(_ values: [Double], _ box: Box) -> (at: (Int, Int) -> Double, mean: Double) {
  // Sums for the normal equations of the fit, with x and y measured from the box's centre.
  var n = 0.0, sx = 0.0, sy = 0.0, sxx = 0.0, syy = 0.0, sxy = 0.0, sv = 0.0, sxv = 0.0, syv = 0.0
  let cx = Double(box.width - 1) / 2, cy = Double(box.height - 1) / 2
  for index in values.indices where isRim(index % box.width, index / box.width, box) {
    let x = Double(index % box.width) - cx, y = Double(index / box.width) - cy, v = values[index]
    n += 1; sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; sv += v; sxv += x * v; syv += y * v
  }
  // The rim is symmetric around the centre, so sx, sy and sxy are about 0 and the fit separates.
  let c = sv / n
  let gx = sxx > 0 ? (sxv - sx * c) / sxx : 0
  let gy = syy > 0 ? (syv - sy * c) / syy : 0
  return ({ x, y in c + gx * (Double(x) - cx) + gy * (Double(y) - cy) }, c)
}

if let until = stillMarkFadesBy, let box = markBox {
  let reader = try AVAssetReader(asset: asset)
  let output = AVAssetReaderTrackOutput(track: videoTrack, outputSettings: pixelFormat)
  reader.add(output)
  reader.startReading()

  // For each frame of the opening stretch: what is left after the steady
  // correction, as brightness above the surroundings, and how much room there
  // is above the surroundings to see anything (none on a white page).
  var leftovers: [(frame: Int, left: [Double], room: Double)] = []
  var frame = 0
  while let sample = output.copyNextSampleBuffer() {
    guard let picture = CMSampleBufferGetImageBuffer(sample) else { continue }
    if CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample)) >= until { break }
    CVPixelBufferLockBaseAddress(picture, .readOnly)
    let base = UnsafePointer(CVPixelBufferGetBaseAddress(picture)!.assumingMemoryBound(to: UInt8.self))
    let corrected = correctedBrightness(base, CVPixelBufferGetBytesPerRow(picture), box)
    CVPixelBufferUnlockBaseAddress(picture, .readOnly)
    let background = slopedBackground(corrected, box)
    let left = corrected.indices.map { corrected[$0] - background.at($0 % box.width, $0 / box.width) }
    leftovers.append((frame, left, 255 - background.mean))
    frame += 1
  }

  // Where to look first: the middle of the film's own logo.
  let peak = alpha.max() ?? 1
  let middle = alpha.indices.filter { alpha[$0] >= peak * 0.6 }
  let levels = leftovers.map { item in median(middle.map { item.left[$0] }) }

  // The shape: the typical leftover, from the frames where the copy clearly shows.
  let clear = leftovers.indices.filter { leftovers[$0].room > 40 && levels[$0] > 6 }
  if clear.count >= 3 {
    stillShape = (0..<(box.width * box.height)).map { index in
      if isRim(index % box.width, index / box.width, box) { return 0 }
      let value = median(clear.map { leftovers[$0].left[index] / levels[$0] })
      return value < 0.08 ? 0 : min(value, 1.5)
    }
    let stillPeak = stillShape.max() ?? 1
    let edge = stillShape.map { $0 > 0 && $0 < stillPeak * 0.9 }
    stillOutline = edge.indices.map { index in
      let x = index % box.width, y = index / box.width
      for dy in -1...1 {
        for dx in -1...1 {
          let nx = x + dx, ny = y + dy
          if nx >= 0, ny >= 0, nx < box.width, ny < box.height, edge[ny * box.width + nx] { return true }
        }
      }
      return false
    }

    // Its strength in every frame of the stretch, measured on its own middle...
    let stillMiddle = stillShape.indices.filter { stillShape[$0] >= 0.6 }
    let raw = leftovers.map { item -> Double? in
      guard item.room > 25 else { return nil } // too bright to tell; there is nothing to see there anyway
      return max(0, median(stillMiddle.map { item.left[$0] / stillShape[$0] }))
    }
    // ...then smoothed over the frame before and after, so the correction fades
    // as smoothly as the copy does. Frames too bright to measure are left out of
    // the average rather than counted as zero, or the copy's first visible
    // frames would be under-corrected.
    for index in raw.indices where raw[index] != nil {
      let near = raw[max(0, index - 1)...min(raw.count - 1, index + 1)].compactMap { $0 }
      let smooth = near.reduce(0, +) / Double(near.count)
      if smooth > 0.5 { stillStrength[leftovers[index].frame] = smooth }
    }
    print(String(format: "Second copy of the logo learned from %d frames; removed in %d frames before %.1f s.",
                 clear.count, stillStrength.count, until))
  } else {
    print(String(format: "No second copy of the logo was found before %.1f s.", until))
  }
}

/// Lifts the logo off one frame, in place.
func eraseMark(in picture: CVPixelBuffer, box: Box, frame: Int) {
  CVPixelBufferLockBaseAddress(picture, [])
  defer { CVPixelBufferUnlockBaseAddress(picture, []) }
  let base = CVPixelBufferGetBaseAddress(picture)!.assumingMemoryBound(to: UInt8.self)
  let rowBytes = CVPixelBufferGetBytesPerRow(picture)
  func offset(_ x: Int, _ y: Int) -> Int { (box.top + y) * rowBytes + (box.left + x) * 4 }

  // real = (seen - a x white) / (1 - a), for every pixel the logo touches.
  for y in 0..<box.height {
    for x in 0..<box.width {
      let a = alpha[y * box.width + x]
      if a == 0 { continue }
      for channel in 0..<3 {
        let real = (Double(base[offset(x, y) + channel]) - a * 255) / (1 - a)
        base[offset(x, y) + channel] = UInt8(min(max(real, 0), 255).rounded())
      }
    }
  }

  // The second copy, during the opening stretch only (see Step 1b).
  let still = stillStrength[frame] ?? 0
  if still > 0 {
    for y in 0..<box.height {
      for x in 0..<box.width {
        let amount = stillShape[y * box.width + x] * still
        if amount == 0 { continue }
        for channel in 0..<3 {
          base[offset(x, y) + channel] = UInt8(min(max(Double(base[offset(x, y) + channel]) - amount, 0), 255).rounded())
        }
      }
    }
  }

  // The soft outline is the hardest part to recover exactly and can leave a
  // hairline trace, so every pixel on it, and one pixel either side of it,
  // becomes the average of its 5 x 5 neighbourhood, which blends the trace away.
  var recovered = [UInt8](repeating: 0, count: box.width * box.height * 3)
  for y in 0..<box.height {
    for x in 0..<box.width {
      for channel in 0..<3 { recovered[(y * box.width + x) * 3 + channel] = base[offset(x, y) + channel] }
    }
  }
  for y in 2..<(box.height - 2) {
    for x in 2..<(box.width - 2) {
      guard outline[y * box.width + x] || (still > 0 && stillOutline[y * box.width + x]) else { continue }
      for channel in 0..<3 {
        var total = 0
        for dy in -2...2 {
          for dx in -2...2 { total += Int(recovered[((y + dy) * box.width + (x + dx)) * 3 + channel]) }
        }
        base[offset(x, y) + channel] = UInt8(total / 25)
      }
    }
  }
}

// --- Step 2: read the clip, fix and enlarge each frame, fade the sound, write ---
let reader = try AVAssetReader(asset: asset)
let videoOutput = AVAssetReaderTrackOutput(track: videoTrack, outputSettings: pixelFormat)
reader.add(videoOutput)

// The sound is read as plain numbers (32-bit floats, channels side by side), so it can be faded.
var audioOutput: AVAssetReaderTrackOutput?
if let track = audioTrack {
  let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
    AVFormatIDKey: kAudioFormatLinearPCM,
    AVLinearPCMBitDepthKey: 32,
    AVLinearPCMIsFloatKey: true,
    AVLinearPCMIsNonInterleaved: false,
    AVLinearPCMIsBigEndianKey: false,
  ])
  reader.add(output)
  audioOutput = output
}

let writer = try AVAssetWriter(outputURL: workingURL, fileType: .mp4)
writer.shouldOptimizeForNetworkUse = true // the index goes first, so the browser can start playing at once

let videoInput = AVAssetWriterInput(mediaType: .video, outputSettings: [
  AVVideoCodecKey: AVVideoCodecType.h264,
  AVVideoWidthKey: outputWidth,
  AVVideoHeightKey: outputHeight,
  AVVideoCompressionPropertiesKey: [
    AVVideoAverageBitRateKey: bitRate,
    AVVideoMaxKeyFrameIntervalKey: 48, // a keyframe every 2 seconds: normal for a clip that only plays forward
    AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
  ],
])
videoInput.expectsMediaDataInRealTime = false
let frameWriter = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: videoInput, sourcePixelBufferAttributes: [
  kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
  kCVPixelBufferWidthKey as String: outputWidth,
  kCVPixelBufferHeightKey as String: outputHeight,
])
writer.add(videoInput)

var audioInput: AVAssetWriterInput?
if audioOutput != nil {
  let input = AVAssetWriterInput(mediaType: .audio, outputSettings: [
    AVFormatIDKey: kAudioFormatMPEG4AAC,
    AVSampleRateKey: 48_000,
    AVNumberOfChannelsKey: 2,
    AVEncoderBitRateKey: 192_000,
  ])
  input.expectsMediaDataInRealTime = false
  writer.add(input)
  audioInput = input
}

reader.startReading()
writer.startWriting()
writer.startSession(atSourceTime: .zero)

/// Core Image does the enlarging on the graphics card.
let imageWorker = CIContext()

/// A 1080p copy of one frame: Lanczos enlargement, then a light sharpen.
func enlarge(_ picture: CVPixelBuffer) -> CVPixelBuffer? {
  var larger: CVPixelBuffer?
  CVPixelBufferPoolCreatePixelBuffer(nil, frameWriter.pixelBufferPool!, &larger)
  guard let output = larger else { return nil }
  let scaled = CIImage(cvPixelBuffer: picture).applyingFilter("CILanczosScaleTransform", parameters: [
    kCIInputScaleKey: Double(outputHeight) / Double(sourceSize.height),
    kCIInputAspectRatioKey: (Double(outputWidth) / Double(outputHeight)) / (Double(sourceSize.width) / Double(sourceSize.height)),
  ])
  let sharpened = scaled.applyingFilter("CIUnsharpMask", parameters: [kCIInputRadiusKey: 1.4, kCIInputIntensityKey: 0.4])
  let wholeFrame = CGRect(x: 0, y: 0, width: outputWidth, height: outputHeight)
  imageWorker.render(sharpened.cropped(to: wholeFrame), to: output, bounds: wholeFrame, colorSpace: CGColorSpace(name: CGColorSpace.itur_709))
  return output
}

/// How loud the sound may be at `time` seconds: rising at the start, dying away at the end.
/// The curve is a quarter sine, which sounds smooth to the ear (no sudden start or stop).
func gain(at time: Double) -> Float {
  let rising = fadeIn > 0 ? min(1, max(0, time / fadeIn)) : 1
  let falling = fadeOut > 0 ? min(1, max(0, (duration - time) / fadeOut)) : 1
  return Float(sin(rising * .pi / 2) * sin(falling * .pi / 2))
}

/// Fades one block of sound, in place.
func fade(_ sample: CMSampleBuffer) {
  guard let format = CMSampleBufferGetFormatDescription(sample),
        let description = CMAudioFormatDescriptionGetStreamBasicDescription(format),
        let block = CMSampleBufferGetDataBuffer(sample) else { return }
  let channels = Int(description.pointee.mChannelsPerFrame)
  let rate = description.pointee.mSampleRate
  let start = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sample))
  var length = 0
  var pointer: UnsafeMutablePointer<Int8>?
  guard CMBlockBufferGetDataPointer(block, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &length, dataPointerOut: &pointer) == noErr,
        let bytes = pointer else { return }
  bytes.withMemoryRebound(to: Float.self, capacity: length / 4) { values in
    let frames = length / 4 / channels
    for frame in 0..<frames {
      let g = gain(at: start + Double(frame) / rate)
      for channel in 0..<channels { values[frame * channels + channel] *= g }
    }
  }
}

// The writer mixes picture and sound together as it goes, so it sometimes asks
// for one before it will take more of the other. Feeding whichever one is
// ready, in turns, keeps both moving.
var videoDone = false
var audioDone = audioOutput == nil
var frameCount = 0
while !(videoDone && audioDone) {
  var fed = false
  if !videoDone && videoInput.isReadyForMoreMediaData {
    if let sample = videoOutput.copyNextSampleBuffer() {
      if let picture = CMSampleBufferGetImageBuffer(sample) {
        if let box = markBox { eraseMark(in: picture, box: box, frame: frameCount) }
        if let larger = enlarge(picture) {
          frameWriter.append(larger, withPresentationTime: CMSampleBufferGetPresentationTimeStamp(sample))
          frameCount += 1
        }
      }
    } else {
      videoInput.markAsFinished()
      videoDone = true
    }
    fed = true
  }
  if !audioDone, let input = audioInput, let output = audioOutput, input.isReadyForMoreMediaData {
    if let sample = output.copyNextSampleBuffer() {
      fade(sample)
      input.append(sample)
    } else {
      input.markAsFinished()
      audioDone = true
    }
    fed = true
  }
  if !fed { usleep(1000) }
}

let finished = DispatchSemaphore(value: 0)
writer.finishWriting { finished.signal() }
finished.wait()
guard writer.status == .completed else {
  print("Writing failed: \(writer.error?.localizedDescription ?? "unknown error")")
  try? FileManager.default.removeItem(at: workingURL)
  exit(1)
}
// Swap the finished film in: replaces the old file in one step, or simply moves it there.
if FileManager.default.fileExists(atPath: videoURL.path) {
  _ = try FileManager.default.replaceItemAt(videoURL, withItemAt: workingURL)
} else {
  try FileManager.default.moveItem(at: workingURL, to: videoURL)
}

let megabytes = Double((try? FileManager.default.attributesOfItem(atPath: videoURL.path)[.size] as? Int) ?? 0) / 1_000_000
print(String(format: "Done: %d frames, %d x %d, %.1f seconds, sound %@, %.1f MB", frameCount, outputWidth, outputHeight, duration,
             audioTrack == nil ? "none" : String(format: "faded in %.1f s / out %.1f s", fadeIn, fadeOut), megabytes))
print("Wrote \(videoURL.path)")

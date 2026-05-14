import Foundation
import Vision
import AppKit

enum OCRLabelError: Error {
    case missingArgument
    case unreadableImage
}

func performOCR(at imagePath: String) throws -> String {
    guard let image = NSImage(contentsOfFile: imagePath) else {
        throw OCRLabelError.unreadableImage
    }

    var imageRect = NSRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(forProposedRect: &imageRect, context: nil, hints: nil) else {
        throw OCRLabelError.unreadableImage
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    let lines = observations.compactMap { observation -> String? in
        observation.topCandidates(1).first?.string
    }

    return lines.joined(separator: "\n")
}

do {
    guard CommandLine.arguments.count >= 2 else {
        throw OCRLabelError.missingArgument
    }

    let text = try performOCR(at: CommandLine.arguments[1])
    FileHandle.standardOutput.write(Data(text.utf8))
} catch OCRLabelError.missingArgument {
    FileHandle.standardError.write(Data("Usage: swift ocr_label.swift <image-path>\n".utf8))
    exit(2)
} catch OCRLabelError.unreadableImage {
    FileHandle.standardError.write(Data("The image could not be opened for OCR.\n".utf8))
    exit(3)
} catch {
    FileHandle.standardError.write(Data("OCR failed: \(error.localizedDescription)\n".utf8))
    exit(1)
}

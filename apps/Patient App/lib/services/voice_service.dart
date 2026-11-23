import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';

/// Speech recognition, behind an interface so widget tests can inject a fake
/// instead of talking to a microphone.
abstract class VoiceService {
  Future<bool> initialize();
  Future<bool> start({
    required void Function(String words, bool finalResult) onWords,
    required void Function(String status) onStatus,
  });
  Future<void> stop();
  Future<void> cancel();
  void dispose();
}

/// Real on-device / platform speech-to-text via the `speech_to_text` plugin.
class DeviceVoiceService implements VoiceService {
  final SpeechToText _speech;
  bool _initialized = false;

  DeviceVoiceService({SpeechToText? speech})
      : _speech = speech ?? SpeechToText();

  @override
  Future<bool> initialize() async {
    if (_initialized && _speech.isAvailable) return true;
    _initialized = await _speech.initialize(
      onStatus: (_) {},
      onError: (_) {},
    );
    return _initialized && _speech.isAvailable;
  }

  @override
  Future<bool> start({
    required void Function(String words, bool finalResult) onWords,
    required void Function(String status) onStatus,
  }) async {
    final ready = await initialize();
    if (!ready) return false;

    await _speech.listen(
      onResult: (SpeechRecognitionResult result) {
        onWords(result.recognizedWords, result.finalResult);
      },
    );
    return true;
  }

  @override
  Future<void> stop() => _speech.stop();

  @override
  Future<void> cancel() => _speech.cancel();

  @override
  void dispose() {
    // SpeechToText has no dispose; cancelling releases the microphone.
    _speech.cancel();
  }
}

/// Used by tests and unsupported platforms: the mic button stays visible but
/// reports that voice input is unavailable, so typing still works.
class NoVoiceService implements VoiceService {
  @override
  Future<bool> initialize() async => false;

  @override
  Future<bool> start({
    required void Function(String words, bool finalResult) onWords,
    required void Function(String status) onStatus,
  }) async =>
      false;

  @override
  Future<void> stop() async {}

  @override
  Future<void> cancel() async {}

  @override
  void dispose() {}
}

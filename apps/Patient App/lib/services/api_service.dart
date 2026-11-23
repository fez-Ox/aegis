import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/memory_answer.dart';

/// Talks to the Aegis gateway. The app only reads memory — it never mutates it.
///
/// `/api/v1/query` is the primary endpoint because it owns place-deduplicated
/// candidates and ambiguity. `/api/v1/ask` is the natural-language fallback for
/// questions the class-level matcher cannot parse.
class ApiService {
  static const requestTimeout = Duration(seconds: 8);
  static const unreachableMessage =
      "Can't reach Aegis memory. Check the connection and try again.";

  /// Message shown when the server cannot be reached, including the address
  /// the app is actually using so a wrong URL is obvious on-device.
  String get unreachableDetail =>
      '$unreachableMessage (server: $baseUrl)';
  static const notFoundMessage = 'Not found. Object not in history';

  /// Mutable so the patient can switch servers from the app without a rebuild
  /// (e.g. a LAN IP at the demo venue instead of the deployed Modal API).
  String baseUrl;
  final http.Client _client;

  ApiService({String? baseUrl, http.Client? client})
      : baseUrl =
            (baseUrl ?? 'http://127.0.0.1:8000').replaceAll(RegExp(r'/+$'), ''),
        _client = client ?? http.Client();

  void setBaseUrl(String url) {
    final trimmed = url.trim();
    if (trimmed.isNotEmpty) {
      baseUrl = trimmed.replaceAll(RegExp(r'/+$'), '');
    }
  }

  /// A typed natural-language question (typed or dictated from the mic).
  Future<MemoryAnswer> ask(String text, {TimeCue cue = TimeCue.now}) async {
    final query = _withCue(text, cue);
    final item = _extractItem(query);
    final title = '“${query.trim()}”';

    final ranked = await _getJson('/api/v1/query', {'item': item});
    final rankedAnswer = MemoryAnswer.fromQuery(
      ranked,
      baseUrl: baseUrl,
      title: title,
      cue: cue,
    );
    if (rankedAnswer.found) return rankedAnswer;

    final phrase = await _getJson('/api/v1/ask', {'text': query});
    final phraseAnswer = MemoryAnswer.fromAsk(
      phrase,
      baseUrl: baseUrl,
      title: title,
      cue: cue,
    );
    if (phraseAnswer.found) return phraseAnswer;

    return _notFound(title, cue);
  }

  /// A tap on one of the object cards: a direct object-history lookup.
  Future<MemoryAnswer> lookupObject(String label, {TimeCue cue = TimeCue.now}) async {
    final title = '“Where is my $label?”';
    final json = await _getJson('/api/v1/query', {'item': label});
    final answer = MemoryAnswer.fromQuery(
      json,
      baseUrl: baseUrl,
      title: title,
      cue: cue,
    );
    if (!answer.found) {
      return _notFound(title, cue);
    }
    return answer;
  }

  /// Objects the active dataset actually has memory for. Used to build the
  /// quick-tap tiles so the grid never advertises objects that don't exist.
  /// Returns an empty list on failure — the caller falls back to presets.
  Future<List<String>> trackedObjects() async {
    try {
      final data = await _getJson('/api/v1/datasets', const {});
      for (final entry in data['datasets'] as List? ?? const []) {
        if (entry is Map && entry['is_active'] == true) {
          return (entry['tracked_objects'] as List? ?? const [])
              .whereType<String>()
              .toList();
        }
      }
      final graph = await _getJson('/api/v1/scene_graph', const {});
      final latest = graph['latest_objects'];
      if (latest is Map) {
        return latest.values
            .whereType<Map>()
            .map((v) => v['label'])
            .whereType<String>()
            .toList();
      }
    } on ApiException {
      // Offline: caller keeps the preset tiles.
    }
    return const [];
  }

  /// Re-ask the same question with a different time cue from the drawer.
  Future<MemoryAnswer> recall(
    String text, {
    required TimeCue cue,
  }) =>
      ask(text, cue: cue);

  MemoryAnswer _notFound(String title, TimeCue cue) => MemoryAnswer(
        title: title,
        found: false,
        summary: notFoundMessage,
        mode: ResolutionMode.notFound,
        candidates: const [],
        cue: cue,
      );

  /// Cheap connectivity probe used by the header's live indicator.
  Future<bool> isServerLive() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/health'))
          .timeout(const Duration(seconds: 4));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// GET a JSON object. A network error or a non-200 reply is a user-facing
  /// failure — it must never be reported to the patient as "not in history".
  Future<Map<String, dynamic>> _getJson(
    String path,
    Map<String, String> params,
  ) async {
    try {
      final uri = Uri.parse('$baseUrl$path').replace(queryParameters: params);
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode != 200) {
        throw ApiException(unreachableDetail);
      }
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw ApiException(unreachableDetail);
      }
      return decoded;
    } on ApiException {
      rethrow;
    } catch (_) {
      throw ApiException(unreachableDetail);
    }
  }

  /// Strip question scaffolding so the class-level matcher sees the noun.
  /// "Where were my keys yesterday?" -> "keys".
  static String _extractItem(String text) {
    var value = text.toLowerCase().trim();
    value = value.replaceAll(RegExp(r'[?.!]+$'), '').trim();
    value = value.replaceFirst(
      RegExp(
        r'^(where|what)\s+(is|are|was|were|did|do)\s+'
        r'(my|the|a|an|our)\s+',
      ),
      '',
    );
    value = value.replaceFirst(RegExp(r'^(where\s+)?(is|are|was|were)\s+'), '');
    value = value.replaceFirst(RegExp(r'^(my|the|a|an|our)\s+'), '');
    for (final cue in [
      ' yesterday',
      ' this morning',
      ' earlier',
      ' today',
      ' last night',
    ]) {
      value = value.replaceFirst(RegExp('$cue\$'), '');
    }
    return value.trim().isEmpty ? text.trim() : value.trim();
  }

  static String _withCue(String text, TimeCue cue) {
    final suffix = cue.querySuffix;
    if (suffix.isEmpty) return text;
    final lower = text.toLowerCase();
    if (lower.contains('yesterday') ||
        lower.contains('morning') ||
        lower.contains('earlier')) {
      return text;
    }
    return '$text$suffix';
  }
}

/// Raised for user-facing errors that must not be swallowed by `_getJson`.
class ApiException implements Exception {
  final String message;
  const ApiException(this.message);

  @override
  String toString() => message;
}

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/memory_answer.dart';

/// Talks to the Aegis gateway. The app only reads memory — it never mutates it.
///
/// `/api/v1/query` is the primary endpoint because it owns place-deduplicated
/// candidates and ambiguity. `/api/v1/ask` is the natural-language fallback for
/// questions the class-level matcher cannot parse.
class ApiService {
  static const String defaultBaseUrl =
      'https://sans42699--aegis-memory-api-serve-memory-api.us-east.modal.run';
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
          .timeout(const Duration(seconds: 8));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// A direct object-location lookup, used by the tracking detail view.
  Future<MemoryAnswer> queryItem(String item) async {
    final json = await _getJson('/api/v1/query', {'item': item});
    return MemoryAnswer.fromQuery(
      json,
      baseUrl: baseUrl,
      title: '“$item”',
    );
  }

  /// Instance id behind a class label, for enrolling a personal item.
  Future<int?> instanceIdFor(String item) async {
    final json = await _getJson('/api/v1/query', {'item': item});
    return json['instance_id'] as int?;
  }

  /// Rename an auto-numbered room. Caregiver labels are persisted by the API.
  Future<void> renameRoom(int roomId, String label) async {
    final uri = Uri.parse('$baseUrl/api/v1/rooms/rename').replace(
      queryParameters: {
        'room_id': '$roomId',
        'label': label,
      },
    );
    final response = await _client.post(uri).timeout(requestTimeout);
    if (response.statusCode != 200) {
      throw ApiException(unreachableDetail);
    }
  }

  /// Enrol an alias for a personal item. Requires a home store on the server.
  Future<void> enrollItem({
    required int instanceId,
    required String alias,
    required String homeId,
    String? canonicalClass,
    String? usualAnchor,
    String? usualRoom,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/enroll');
    final response = await _client
        .post(
          uri,
          headers: {'content-type': 'application/json'},
          body: jsonEncode({
            'instance_id': instanceId,
            'alias': alias,
            'home_id': homeId,
            if (canonicalClass != null) 'canonical_class': canonicalClass,
            if (usualAnchor != null) 'usual_anchor': usualAnchor,
            if (usualRoom != null) 'usual_room': usualRoom,
          }),
        )
        .timeout(requestTimeout);
    if (response.statusCode != 200) {
      throw ApiException('Could not enrol item (${response.statusCode}).');
    }
  }

  /// Live capture status, if the gateway exposes a capture session.
  Future<Map<String, dynamic>> captureStatus() =>
      _getJson('/api/v1/capture/status', const {});

  /// Health summary used by the System Status tab and the live badge.
  Future<Map<String, dynamic>> health() => _getJson('/api/v1/health', const {});

  /// Per-dataset summary including tracked objects and readiness.
  Future<Map<String, dynamic>> datasets() => _getJson('/api/v1/datasets', const {});

  /// Room regions with their anchors and objects, from the active dataset.
  Future<List<Map<String, dynamic>>> rooms() async {
    final data = await _getRaw('/api/v1/rooms', const {});
    if (data is! List) return const [];
    return data
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  /// Object sighting events. The endpoint has no object filter, so callers
  /// filter the returned list by object label on device.
  Future<List<Map<String, dynamic>>> timeline() async {
    final data = await _getRaw('/api/v1/timeline', const {});
    if (data is! List) return const [];
    return data
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  /// GET a JSON object. A network error or a non-200 reply is a user-facing
  /// failure — it must never be reported to the patient as "not in history".
  Future<Map<String, dynamic>> _getJson(
    String path,
    Map<String, String> params,
  ) async {
    final decoded = await _getRaw(path, params);
    if (decoded is! Map<String, dynamic>) {
      throw ApiException(unreachableDetail);
    }
    return decoded;
  }

  /// GET decoded JSON of any shape; network/HTTP errors are user-facing.
  Future<dynamic> _getRaw(
    String path,
    Map<String, String> params,
  ) async {
    try {
      final uri = Uri.parse('$baseUrl$path').replace(queryParameters: params);
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode != 200) {
        throw ApiException(unreachableDetail);
      }
      return jsonDecode(response.body);
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

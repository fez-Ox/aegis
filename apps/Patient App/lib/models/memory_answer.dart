// The shape the patient UI consumes, regardless of which Aegis endpoint
// produced it. The server already computes ambiguity/ranking; we only map its
// JSON onto friendly, immutable Dart objects.

/// A human-friendly mapping of the server's `resolution_mode`.
enum ResolutionMode { direct, ranked, ambiguous, notFound }

extension ResolutionModeX on ResolutionMode {
  /// The badge copy from the mockup — never a raw probability.
  String get badge => switch (this) {
        ResolutionMode.direct => 'Found it',
        ResolutionMode.ranked => 'Best guess',
        ResolutionMode.ambiguous => 'I’m not sure — which one?',
        ResolutionMode.notFound => 'I’m not sure',
      };

  bool get isFound => this != ResolutionMode.notFound;

  static ResolutionMode fromServer(String? value, {required bool found}) {
    if (!found) return ResolutionMode.notFound;
    return switch (value) {
      'disambiguate' || 'ambiguous' => ResolutionMode.ambiguous,
      'ranked' => ResolutionMode.ranked,
      'direct' => ResolutionMode.direct,
      _ => ResolutionMode.direct,
    };
  }
}

/// A time cue chosen in the answer drawer. It is appended to natural-language
/// queries (the server has no `as_of` parameter yet) so T3-style questions work
/// without pretending to have exact-timestamp precision.
enum TimeCue { now, morning, yesterday }

extension TimeCueX on TimeCue {
  String get label => switch (this) {
        TimeCue.now => 'Now',
        TimeCue.morning => 'This morning',
        TimeCue.yesterday => 'Yesterday',
      };

  String get querySuffix => switch (this) {
        TimeCue.now => '',
        TimeCue.morning => ' this morning',
        TimeCue.yesterday => ' yesterday',
      };
}

/// One place the object might be. At most three are shown, matching the
/// pipeline's place-deduplicated candidates.
class MemoryCandidate {
  final String place;
  final String detail;
  final String seen;
  final String? cropUrl;
  final double score;
  final String? instanceLabel;

  const MemoryCandidate({
    required this.place,
    required this.detail,
    required this.seen,
    this.cropUrl,
    this.score = 0,
    this.instanceLabel,
  });

  factory MemoryCandidate.fromJson(Map<String, dynamic> json, String baseUrl) {
    final anchor = json['anchor_label'] as String?;
    final room = json['room_label'] as String?;
    final relation = json['relation'] as String?;

    final place = anchor ?? room ?? 'Somewhere in the home';
    final detailParts = <String>[
      if (relation != null && relation.isNotEmpty) relation,
      if (anchor != null && room != null && room.isNotEmpty) room,
    ];
    final detail = detailParts.join(' · ');

    final rawCrop = json['crop_url'] as String?;
    final seen = (json['last_seen_at'] as String?) ??
        (json['last_seen_wallclock'] as String?) ??
        '';

    return MemoryCandidate(
      place: place,
      detail: detail,
      seen: seen,
      cropUrl:
          (rawCrop == null || rawCrop.isEmpty) ? null : _absolute(baseUrl, rawCrop),
      score: (json['score'] as num?)?.toDouble() ?? 0,
      instanceLabel: json['label'] as String?,
    );
  }

  static String _absolute(String baseUrl, String path) =>
      path.startsWith('http') ? path : '$baseUrl$path';
}

/// Everything the drawer needs to render one answer.
class MemoryAnswer {
  final String title;
  final bool found;
  final String summary;
  final ResolutionMode mode;
  final List<MemoryCandidate> candidates;
  final TimeCue cue;
  final String? rawAnswer;

  const MemoryAnswer({
    required this.title,
    required this.found,
    required this.summary,
    required this.mode,
    required this.candidates,
    this.cue = TimeCue.now,
    this.rawAnswer,
  });

  /// Build from `/api/v1/query`, which owns candidates and ambiguity.
  factory MemoryAnswer.fromQuery(
    Map<String, dynamic> json, {
    required String baseUrl,
    required String title,
    TimeCue cue = TimeCue.now,
  }) {
    final found = json['found'] as bool? ?? false;
    final candidates = <MemoryCandidate>[];
    for (final item in json['candidates'] as List? ?? const []) {
      if (item is Map) {
        candidates.add(
          MemoryCandidate.fromJson(Map<String, dynamic>.from(item), baseUrl),
        );
      }
    }

    var mode = ResolutionModeX.fromServer(
      json['resolution_mode'] as String?,
      found: found,
    );
    if (json['is_ambiguous'] as bool? ?? false) {
      mode = ResolutionMode.ambiguous;
    }

    // One confident answer still has a single candidate: treat it as direct.
    if (mode == ResolutionMode.direct && candidates.length > 1) {
      mode = ResolutionMode.ranked;
    }

    var summary = (json['location_summary'] as String?) ?? '';
    if (summary.isEmpty) {
      summary = (json['explanation'] as String?) ?? '';
    }

    return MemoryAnswer(
      title: title,
      found: found,
      summary: summary,
      mode: mode,
      candidates: candidates,
      cue: cue,
    );
  }

  /// Build from `/api/v1/ask`, which gives a friendlier sentence and evidence.
  factory MemoryAnswer.fromAsk(
    Map<String, dynamic> json, {
    required String baseUrl,
    required String title,
    TimeCue cue = TimeCue.now,
  }) {
    final found = json['found'] as bool? ?? false;
    final answer = (json['answer'] as String?) ?? '';
    final anchor = json['anchor_label'] as String?;
    final room = json['room_label'] as String?;
    final placeParts = <String>[
      if (anchor != null && anchor.isNotEmpty) anchor,
      if (room != null && room.isNotEmpty) room,
    ];
    final seen = json['last_seen_wallclock'] as String?;

    final place = placeParts.join(' · ');
    final candidates = <MemoryCandidate>[];
    if (found) {
      String? crop;
      for (final item in json['evidence'] as List? ?? const []) {
        if (item is Map) {
          final url = item['crop_url'];
          if (url is String && url.isNotEmpty) {
            crop = url.startsWith('http') ? url : '$baseUrl$url';
            break;
          }
        }
      }
      candidates.add(
        MemoryCandidate(
          place: place.isEmpty ? 'In your home' : place,
          detail: answer,
          seen: seen ?? '',
          cropUrl: crop,
        ),
      );
    }

    return MemoryAnswer(
      title: title,
      found: found,
      summary: answer,
      mode: found ? ResolutionMode.direct : ResolutionMode.notFound,
      candidates: candidates,
      cue: cue,
      rawAnswer: answer,
    );
  }
}

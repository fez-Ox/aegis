/// One answer from the Aegis `/api/v1/ask` endpoint.
class AskResult {
  final String answer;
  final bool abstained;
  final String? abstainReason;
  final String? anchorLabel;
  final String? roomLabel;
  final String? relation;
  final String? lastSeenWallclock;
  final String? cropUrl;
  final List<dynamic> evidence;

  const AskResult({
    required this.answer,
    required this.abstained,
    this.abstainReason,
    this.anchorLabel,
    this.roomLabel,
    this.relation,
    this.lastSeenWallclock,
    this.cropUrl,
    this.evidence = const [],
  });

  factory AskResult.fromJson(Map<String, dynamic> json) {
    return AskResult(
      answer: (json['answer'] as String?) ?? '',
      abstained: (json['abstained'] as bool?) ?? !(json['found'] as bool? ?? false),
      abstainReason: json['abstain_reason'] as String?,
      anchorLabel: json['anchor_label'] as String?,
      roomLabel: json['room_label'] as String?,
      relation: json['relation'] as String?,
      lastSeenWallclock: json['last_seen_wallclock'] as String?,
      cropUrl: json['crop_url'] as String?,
      evidence: (json['evidence'] as List?) ?? const [],
    );
  }

  String get statusLabel {
    if (abstained) return 'NOT SURE';
    return 'ANSWER';
  }
}

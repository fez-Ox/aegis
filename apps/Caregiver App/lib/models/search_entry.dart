/// One caregiver-visible query and its outcome, kept on-device.
class SearchEntry {
  final String query;
  final String answer;
  final String at; // ISO-8601
  final String mode;
  final String? tier;
  final bool ambiguous;
  final List<String> candidates;

  const SearchEntry({
    required this.query,
    required this.answer,
    required this.at,
    required this.mode,
    this.tier,
    this.ambiguous = false,
    this.candidates = const [],
  });

  Map<String, dynamic> toJson() => {
        'query': query,
        'answer': answer,
        'at': at,
        'mode': mode,
        'tier': tier,
        'ambiguous': ambiguous,
        'candidates': candidates,
      };

  factory SearchEntry.fromJson(Map<String, dynamic> json) => SearchEntry(
        query: (json['query'] as String?) ?? '',
        answer: (json['answer'] as String?) ?? '',
        at: (json['at'] as String?) ?? '',
        mode: (json['mode'] as String?) ?? 'none',
        tier: json['tier'] as String?,
        ambiguous: (json['ambiguous'] as bool?) ?? false,
        candidates: (json['candidates'] as List? ?? const [])
            .whereType<String>()
            .toList(),
      );
}

class PatientSearchRecord {
  final String? datasetId;
  final String query;
  final bool found;
  final String locationSummary;
  final String? anchorLabel;
  final String? instanceLabel;
  final String timeAgo;
  final DateTime timestamp;
  final bool isPersistentMemory;

  const PatientSearchRecord({
    this.datasetId,
    required this.query,
    required this.found,
    required this.locationSummary,
    this.anchorLabel,
    this.instanceLabel,
    required this.timeAgo,
    required this.timestamp,
    this.isPersistentMemory = false,
  });

  Map<String, dynamic> toJson() => {
    'dataset_id': datasetId,
    'query': query,
    'found': found,
    'location_summary': locationSummary,
    'anchor_label': anchorLabel,
    'instance_label': instanceLabel,
    'time_ago': timeAgo,
    'timestamp': timestamp.toIso8601String(),
    'is_persistent_memory': isPersistentMemory,
  };

  factory PatientSearchRecord.fromJson(Map<String, dynamic> json) => PatientSearchRecord(
    datasetId: json['dataset_id'] as String?,
    query: json['query'] as String,
    found: json['found'] as bool? ?? false,
    locationSummary: json['location_summary'] as String? ?? '',
    anchorLabel: json['anchor_label'] as String?,
    instanceLabel: json['instance_label'] as String?,
    timeAgo: json['time_ago'] as String? ?? 'Just now',
    timestamp: json['timestamp'] != null ? DateTime.parse(json['timestamp'] as String) : DateTime.now(),
    isPersistentMemory: json['is_persistent_memory'] as bool? ?? false,
  );
}

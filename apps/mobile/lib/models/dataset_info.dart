class DatasetInfo {
  final String datasetId;
  final String title;
  final List<String> anchors;
  final List<String> trackedObjects;
  final int numEvents;
  final int numTimelineFrames;
  final bool isActive;

  const DatasetInfo({
    required this.datasetId,
    required this.title,
    required this.anchors,
    required this.trackedObjects,
    this.numEvents = 0,
    this.numTimelineFrames = 0,
    this.isActive = false,
  });

  factory DatasetInfo.fromJson(Map<String, dynamic> json) {
    return DatasetInfo(
      datasetId: json['dataset_id'] as String? ?? '',
      title: json['title'] as String? ?? json['dataset_id'] as String? ?? 'Dataset',
      anchors: (json['anchors'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      trackedObjects: (json['tracked_objects'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      numEvents: json['num_events'] as int? ?? 0,
      numTimelineFrames: json['num_timeline_frames'] as int? ?? 0,
      isActive: json['is_active'] as bool? ?? false,
    );
  }
}

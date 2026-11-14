import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// "Recording" row with a pause switch (FR1.3).
///
/// Hidden unless the server reports a configured live capture.
class CaptureControl extends StatefulWidget {
  final ApiService apiService;

  const CaptureControl({super.key, required this.apiService});

  @override
  State<CaptureControl> createState() => _CaptureControlState();
}

class _CaptureControlState extends State<CaptureControl> {
  CaptureStatus? _status;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final status = await widget.apiService.fetchCaptureStatus();
    if (mounted) {
      setState(() => _status = status);
    }
  }

  Future<void> _toggle(bool recording) async {
    setState(() => _busy = true);
    final status = await widget.apiService.setCapturePaused(!recording);
    if (mounted) {
      setState(() {
        _busy = false;
        if (status != null) {
          _status = status;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    if (status == null || !status.available) {
      return const SizedBox.shrink();
    }
    final recording = !status.paused;
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.darkSurface,
        borderRadius: BorderRadius.circular(AppTheme.cardCornerRadius),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: [
          Icon(
            recording ? Icons.fiber_manual_record_rounded : Icons.pause_circle_rounded,
            color: recording ? AppTheme.systemRed : AppTheme.alertAmber,
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              recording ? 'Recording' : 'Paused',
              style: TextStyle(
                color: recording ? AppTheme.textHighContrast : AppTheme.alertAmber,
                fontSize: 15,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Switch(
            value: recording,
            onChanged: _busy ? null : _toggle,
          ),
        ],
      ),
    );
  }
}

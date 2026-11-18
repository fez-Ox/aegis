import 'package:flutter/material.dart';

import '../models/ask_result.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// The only screen: ask a question, see the grounded answer.
class AskScreen extends StatefulWidget {
  final ApiService apiService;

  const AskScreen({super.key, required this.apiService});

  @override
  State<AskScreen> createState() => _AskScreenState();
}

class _AskScreenState extends State<AskScreen> {
  final _controller = TextEditingController();
  AskResult? _result;
  bool _loading = false;
  bool _unreachable = false;

  Future<void> _ask() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;
    setState(() {
      _loading = true;
      _unreachable = false;
    });
    final result = await widget.apiService.ask(text);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _result = result;
      _unreachable = result == null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.lightCanvas,
      appBar: AppBar(
        title: const Text('Aegis Memory'),
        backgroundColor: AppTheme.lightSurface,
        foregroundColor: AppTheme.textHighContrast,
        elevation: 0,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Ask where something is', style: AppTheme.title1),
              const SizedBox(height: 4),
              const Text(
                'Aegis answers from what it remembers seeing.',
                style: TextStyle(fontSize: 15, color: AppTheme.textMuted),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('ask-field'),
                      controller: _controller,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _ask(),
                      decoration: const InputDecoration(
                        hintText: 'Where are my keys?',
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(horizontal: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    height: AppTheme.minTouchTarget,
                    child: FilledButton(
                      key: const Key('ask-send'),
                      onPressed: _loading ? null : _ask,
                      child: _loading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.send),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              Expanded(child: _buildAnswer()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAnswer() {
    if (_unreachable) {
      return Card(
        color: AppTheme.lightSurface,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            ApiService.unreachableMessage,
            style: const TextStyle(fontSize: 17, color: AppTheme.textHighContrast),
          ),
        ),
      );
    }
    final result = _result;
    if (result == null) {
      return const Center(
        child: Text('Ask a question to search your memory.', style: TextStyle(color: AppTheme.textMuted)),
      );
    }
    final place = [
      if (result.anchorLabel != null) result.anchorLabel,
      if (result.roomLabel != null) result.roomLabel,
    ].join(', ');
    String? crop;
    for (final item in result.evidence) {
      final url = item is Map ? item['crop_url'] : null;
      if (url is String && url.isNotEmpty) {
        crop = widget.apiService.evidenceUrl(url);
        break;
      }
    }
    return SingleChildScrollView(
      child: Card(
        color: AppTheme.lightSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppTheme.cardCornerRadius),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Chip(
                label: Text(result.statusLabel),
                backgroundColor: result.abstained
                    ? AppTheme.segmentedTrack
                    : const Color(0xFFDCFCE7),
              ),
              const SizedBox(height: 8),
              Text(result.answer, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
              if (place.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text('Place: $place', style: const TextStyle(color: AppTheme.textMuted)),
              ],
              if (result.lastSeenWallclock != null)
                Text('Last seen: ${result.lastSeenWallclock}',
                    style: const TextStyle(color: AppTheme.textMuted)),
              if (crop != null) ...[
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    crop,
                    height: 180,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

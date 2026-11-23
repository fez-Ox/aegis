import 'package:flutter/material.dart';

import '../models/memory_answer.dart';
import '../models/object_tile.dart';
import '../theme/app_theme.dart';
import '../widgets/candidate_card.dart';

/// The "Memory recall" bottom sheet from the mockup. It never shows a naked
/// probability: a labelled badge carries resolution_mode instead.
class AnswerDrawer extends StatefulWidget {
  final MemoryAnswer answer;
  final ObjectKind kind;
  final ValueChanged<TimeCue> onTimeCue;
  final VoidCallback onClose;

  const AnswerDrawer({
    super.key,
    required this.answer,
    required this.kind,
    required this.onTimeCue,
    required this.onClose,
  });

  @override
  State<AnswerDrawer> createState() => _AnswerDrawerState();
}

class _AnswerDrawerState extends State<AnswerDrawer> {
  bool _showOtherPlaces = false;

  @override
  void didUpdateWidget(covariant AnswerDrawer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.answer.title != widget.answer.title ||
        oldWidget.answer.cue != widget.answer.cue) {
      _showOtherPlaces = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final answer = widget.answer;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildHeader(answer),
            const SizedBox(height: 16),
            Flexible(child: SingleChildScrollView(child: _buildBody(answer))),
            const SizedBox(height: 12),
            _buildTimeRow(answer),
            const SizedBox(height: 12),
            SizedBox(
              height: 52,
              child: FilledButton(
                key: const Key('answer-close'),
                onPressed: widget.onClose,
                child: const Text('Got it, thank you'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(MemoryAnswer answer) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'MEMORY RECALL',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1,
                  color: PatientTheme.ochre,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                answer.title,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
              const SizedBox(height: 10),
              _Badge(mode: answer.mode),
            ],
          ),
        ),
        SizedBox(
          width: PatientTheme.touchTarget,
          height: PatientTheme.touchTarget,
          child: IconButton(
            key: const Key('answer-dismiss'),
            tooltip: 'Close',
            onPressed: widget.onClose,
            icon: const Icon(Icons.close, size: 20),
            style: IconButton.styleFrom(
              backgroundColor: PatientTheme.border,
              foregroundColor: PatientTheme.ivory300,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBody(MemoryAnswer answer) {
    if (!answer.found || answer.candidates.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(18),
        decoration: PatientTheme.insetCard(),
        child: Row(
          children: [
            const Icon(
              Icons.search_off_rounded,
              color: PatientTheme.ivory400,
              size: 28,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                answer.summary,
                key: const Key('not-found-message'),
                style: const TextStyle(
                  fontSize: 16,
                  color: PatientTheme.ivory,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final candidates = answer.candidates;
    if (answer.mode == ResolutionMode.ambiguous) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'It could be in one of these places:',
            style: TextStyle(fontSize: 16, color: PatientTheme.ivory300),
          ),
          const SizedBox(height: 12),
          ...List.generate(candidates.length, (i) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: CandidateCard(
                candidate: candidates[i],
                kind: widget.kind,
                tag: i == 0 ? 'Most likely' : null,
              ),
            );
          }),
        ],
      );
    }

    if (answer.mode == ResolutionMode.ranked && candidates.length > 1) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          CandidateCard(candidate: candidates.first, kind: widget.kind, large: true),
          const SizedBox(height: 12),
          if (!_showOtherPlaces)
            SizedBox(
              height: 48,
              child: OutlinedButton(
                key: const Key('other-places'),
                onPressed: () => setState(() => _showOtherPlaces = true),
                child: const Text('Not there? See other places'),
              ),
            ),
          if (_showOtherPlaces)
            ...candidates.skip(1).map(
                  (candidate) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: CandidateCard(candidate: candidate, kind: widget.kind),
                  ),
                ),
        ],
      );
    }

    return CandidateCard(
      candidate: candidates.first,
      kind: widget.kind,
      large: true,
    );
  }

  Widget _buildTimeRow(MemoryAnswer answer) {
    final isNow = answer.cue == TimeCue.now;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (isNow)
          const Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text(
              'Was it somewhere else earlier?',
              style: TextStyle(fontSize: 14, color: PatientTheme.ivory300),
            ),
          ),
        Row(
          children: [
            if (isNow) ...[
              Expanded(
                child: _timeButton(
                  key: const Key('cue-morning'),
                  label: 'This morning',
                  cue: TimeCue.morning,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _timeButton(
                  key: const Key('cue-yesterday'),
                  label: 'Yesterday',
                  cue: TimeCue.yesterday,
                ),
              ),
            ] else
              _timeButton(
                key: const Key('cue-now'),
                label: 'Back to now',
                cue: TimeCue.now,
              ),
          ],
        ),
      ],
    );
  }

  Widget _timeButton({required Key key, required String label, required TimeCue cue}) {
    return SizedBox(
      height: 48,
      child: OutlinedButton(
        key: key,
        onPressed: () => widget.onTimeCue(cue),
        style: OutlinedButton.styleFrom(
          foregroundColor: PatientTheme.ivory300,
          side: const BorderSide(color: PatientTheme.borderStrong),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        child: Text(label, style: const TextStyle(fontSize: 14)),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final ResolutionMode mode;
  const _Badge({required this.mode});

  @override
  Widget build(BuildContext context) {
    final found = mode.isFound;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: found ? PatientTheme.emeraldSurface : PatientTheme.border,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: found ? PatientTheme.emerald : PatientTheme.borderStrong,
        ),
      ),
      child: Text(
        mode.badge,
        key: const Key('resolution-badge'),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: found ? PatientTheme.emerald : PatientTheme.ivory300,
        ),
      ),
    );
  }
}

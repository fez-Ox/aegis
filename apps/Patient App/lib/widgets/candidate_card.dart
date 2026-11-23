import 'package:flutter/material.dart';

import '../models/memory_answer.dart';
import '../models/object_tile.dart';
import '../theme/app_theme.dart';
import 'object_icon.dart';

/// One candidate place in the answer drawer. Mirrors `card()` in patient.html:
/// a photo on the left, place/detail/time on the right.
class CandidateCard extends StatelessWidget {
  final MemoryCandidate candidate;
  final ObjectKind kind;
  final bool large;
  final String? tag;

  const CandidateCard({
    super.key,
    required this.candidate,
    required this.kind,
    this.large = false,
    this.tag,
  });

  @override
  Widget build(BuildContext context) {
    final photo = _buildPhoto(context);
    return Container(
      decoration: PatientTheme.insetCard(color: PatientTheme.surfaceRaised),
      clipBehavior: Clip.antiAlias,
      child: large
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(height: 160, child: photo),
                _buildText(),
              ],
            )
          : Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                SizedBox(width: 104, height: 112, child: photo),
                Expanded(child: _buildText()),
              ],
            ),
    );
  }

  Widget _buildPhoto(BuildContext context) {
    final tone = toneFor(kind);
    final url = candidate.cropUrl;
    if (url != null) {
      return Image.network(
        url,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => _placeholder(tone),
        loadingBuilder: (context, child, progress) {
          if (progress == null) return child;
          return _placeholder(tone);
        },
      );
    }
    return _placeholder(tone);
  }

  Widget _placeholder(List<Color> tone) => Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: tone,
          ),
        ),
        child: Center(
          child: Icon(
            iconFor(kind),
            size: 44,
            color: PatientTheme.ochreLight.withValues(alpha: 0.85),
          ),
        ),
      );

  Widget _buildText() {
    return Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (tag != null) ...[
            Text(
              tag!,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
                color: PatientTheme.ochre,
              ),
            ),
            const SizedBox(height: 5),
          ],
          Text(
            candidate.place,
            style: TextStyle(
              fontSize: large ? 22 : 18,
              fontWeight: FontWeight.w700,
              color: PatientTheme.ivory,
            ),
          ),
          if (candidate.detail.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              candidate.detail,
              style: const TextStyle(
                fontSize: 14,
                color: PatientTheme.ivory300,
              ),
            ),
          ],
          if (candidate.seen.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              candidate.seen,
              style: const TextStyle(
                fontSize: 12,
                color: PatientTheme.ivory400,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

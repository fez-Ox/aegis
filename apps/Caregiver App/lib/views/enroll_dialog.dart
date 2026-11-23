import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../theme/app_theme.dart';

/// "Add a personal item" from the caregiver mockup. Enrolment needs a home
/// store on the server; failures are shown honestly instead of faked.
class EnrollDialog extends StatefulWidget {
  final ApiService apiService;
  final List<String> objectLabels;
  final List<String> roomLabels;

  const EnrollDialog({
    super.key,
    required this.apiService,
    required this.objectLabels,
    required this.roomLabels,
  });

  @override
  State<EnrollDialog> createState() => _EnrollDialogState();
}

class _EnrollDialogState extends State<EnrollDialog> {
  final _alias = TextEditingController();
  final _home = TextEditingController(text: 'home01');
  String? _object;
  String? _room;
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _object = widget.objectLabels.isEmpty ? null : widget.objectLabels.first;
    _room = widget.roomLabels.isEmpty ? null : widget.roomLabels.first;
  }

  @override
  void dispose() {
    _alias.dispose();
    _home.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_object == null || _alias.text.trim().isEmpty) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final id = await widget.apiService.instanceIdFor(_object!);
      if (id == null) {
        setState(() => _message = 'No instance found for $_object.');
        return;
      }
      await widget.apiService.enrollItem(
        instanceId: id,
        alias: _alias.text.trim(),
        homeId: _home.text.trim(),
        canonicalClass: _object,
        usualRoom: _room,
      );
      if (!mounted) return;
      Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _message = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _dropdown(String label, String? value, List<String> items,
          ValueChanged<String?> onChanged) =>
      DropdownButtonFormField<String>(
        key: Key('enroll-$label'),
        initialValue: value,
        items: items
            .map((item) => DropdownMenuItem(value: item, child: Text(item)))
            .toList(),
        onChanged: onChanged,
        decoration: InputDecoration(labelText: label),
        dropdownColor: PatientTheme.surfaceCard,
        style: const TextStyle(color: PatientTheme.ivory, fontSize: 14),
      );

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: PatientTheme.surfaceCard,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(PatientTheme.radiusLarge),
        side: const BorderSide(color: PatientTheme.borderStrong),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Add a personal item',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: PatientTheme.ivory,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'So “my glasses” means exactly these glasses.',
              style: TextStyle(fontSize: 12, color: PatientTheme.ivory400),
            ),
            const SizedBox(height: 18),
            TextField(
              key: const Key('enroll-alias'),
              controller: _alias,
              style: const TextStyle(color: PatientTheme.ivory),
              decoration: const InputDecoration(
                labelText: 'Name, e.g. Reading glasses',
              ),
            ),
            const SizedBox(height: 12),
            _dropdown(
              'Class',
              _object,
              widget.objectLabels,
              (value) => setState(() => _object = value),
            ),
            const SizedBox(height: 12),
            _dropdown(
              'Usual place',
              _room,
              widget.roomLabels,
              (value) => setState(() => _room = value),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('enroll-home'),
              controller: _home,
              style: const TextStyle(color: PatientTheme.ivory),
              decoration: const InputDecoration(labelText: 'Home store id'),
            ),
            if (_message != null) ...[
              const SizedBox(height: 10),
              Text(
                _message!,
                style: const TextStyle(color: Colors.redAccent, fontSize: 12),
              ),
            ],
            const SizedBox(height: 18),
            SizedBox(
              height: 52,
              child: FilledButton(
                key: const Key('enroll-save'),
                onPressed: _busy ? null : _save,
                child: const Text('Save item'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

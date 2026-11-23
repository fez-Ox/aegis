import 'package:url_launcher/url_launcher.dart';

/// Places real phone calls / messages. Kept behind an interface so widget tests
/// never open the device dialer.
abstract class CallService {
  Future<bool> call(String phone);
  Future<bool> message(String phone, String body);
}

class DeviceCallService implements CallService {
  @override
  Future<bool> call(String phone) => _launch(Uri.parse('tel:$phone'));

  @override
  Future<bool> message(String phone, String body) => _launch(
        Uri.parse('sms:$phone').replace(queryParameters: {'body': body}),
      );

  Future<bool> _launch(Uri uri) async {
    if (!await canLaunchUrl(uri)) return false;
    return launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}

class NoCallService implements CallService {
  @override
  Future<bool> call(String phone) async => true;

  @override
  Future<bool> message(String phone, String body) async => true;
}

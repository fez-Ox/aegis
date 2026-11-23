import 'package:flutter/material.dart';

/// Warm espresso / ochre palette taken from the patient HTML mockup.
///
/// The palette lives in one place so the mockup can be checked against the
/// running app without hunting for hard-coded colours in every widget.
class PatientTheme {
  static const Color canvas = Color(0xFF14100A); // espresso-950
  static const Color surface = Color(0xFF1B160F); // espresso-900
  static const Color surfaceRaised = Color(0xFF221C13); // espresso-850
  static const Color surfaceCard = Color(0xFF2A2318); // espresso-800
  static const Color border = Color(0xFF382E1F); // espresso-700
  static const Color borderStrong = Color(0xFF4A3D29); // espresso-600

  static const Color ochre = Color(0xFFF5B82E); // ochre-400
  static const Color ochreLight = Color(0xFFFCD34D); // ochre-300
  static const Color ochreDeep = Color(0xFFB87D14); // ochre-600
  static const Color ivory = Color(0xFFFAF5EB); // ivory-100
  static const Color ivory300 = Color(0xFFCFC0A6); // ivory-300
  static const Color ivory400 = Color(0xFFA39276); // ivory-400

  static const Color emerald = Color(0xFF6EE7B7);
  static const Color emeraldSurface = Color(0xFF022C22);

  /// Apple HIG minimum hit target — the mockup's 44px buttons map to this.
  static const double touchTarget = 44.0;
  static const double radius = 16.0;
  static const double radiusLarge = 24.0;

  static ThemeData get theme {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary: ochre,
        onPrimary: canvas,
        surface: surfaceCard,
        onSurface: ivory,
        surfaceTint: Colors.transparent,
        error: Color(0xFFFF8A80),
      ),
      scaffoldBackgroundColor: canvas,
      dividerColor: border,
      fontFamily: 'Inter',
      textTheme: const TextTheme(
        displaySmall: TextStyle(
          fontSize: 30,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
          color: ivory,
        ),
        titleLarge: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.2,
          color: ivory,
        ),
        titleMedium: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: ivory,
        ),
        bodyLarge: TextStyle(fontSize: 16, color: ivory, height: 1.4),
        bodyMedium: TextStyle(fontSize: 14, color: ivory300, height: 1.4),
        bodySmall: TextStyle(fontSize: 12, color: ivory400),
        labelLarge: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: ivory,
        ),
        labelSmall: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.8,
          color: ochre,
        ),
      ),
    );

    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: surfaceRaised,
        foregroundColor: ivory,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      cardTheme: CardThemeData(
        color: surfaceCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
          side: const BorderSide(color: border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceCard,
        hintStyle: const TextStyle(color: ivory400, fontSize: 16),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: const BorderSide(color: ochre, width: 2),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: ochre,
          foregroundColor: canvas,
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(touchTarget, touchTarget),
          foregroundColor: ochreLight,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          minimumSize: const Size(touchTarget, touchTarget),
          foregroundColor: ivory300,
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: surfaceCard,
        modalBackgroundColor: surfaceCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(radiusLarge),
          ),
        ),
      ),
    );
  }

  /// A soft inset card used for grouped content in the answer drawer.
  static BoxDecoration insetCard({Color color = surfaceRaised}) => BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: border),
      );
}

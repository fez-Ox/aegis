import 'package:flutter/material.dart';

class AppTheme {
  // Apple HIG Semantic Palette (Grounded in HIG Color & Materials)
  static const Color darkCanvas = Color(0xFFFAF7F0);      // System Grouped Canvas (Warm Off-White)
  static const Color darkSurface = Color(0xFFFFFFFF);     // Secondary Grouped Background (Pure White Card)
  static const Color lightCanvas = Color(0xFFFAF7F0);     // System Grouped Canvas
  static const Color lightSurface = Color(0xFFFFFFFF);    // Secondary Grouped Card Surface

  static const Color primaryTeal = Color(0xFFD97706);     // Primary Amber Brand Tone
  static const Color tealAccent = Color(0xFFEAB308);      // Bright Golden Accent
  static const Color royalAmethyst = Color(0xFFCA8A04);   // Deep Ochre Accent
  static const Color alertAmber = Color(0xFFF59E0B);      // System Attention Amber
  static const Color textHighContrast = Color(0xFF1C1917); // HIG Label (Stone-900 WCAG AAA 14:1)
  static const Color textMuted = Color(0xFF78716C);       // HIG Secondary Label (Stone-500)
  static const Color cardBorder = Color(0xFFE7E0D3);      // HIG Hairline Separator

  // iOS System Tints
  static const Color systemBlue = Color(0xFF007AFF);
  static const Color systemIndigo = Color(0xFF5856D6);
  static const Color systemGreen = Color(0xFF34C759);
  static const Color systemOrange = Color(0xFFFF9500);
  static const Color systemRed = Color(0xFFFF3B30);
  static const Color tertiaryLabel = Color(0xFFA8A29E);
  static const Color segmentedThumb = Color(0xFFFFFFFF);
  static const Color segmentedTrack = Color(0xFFECE7DE);

  // HIG Layout & Touch Standards
  static const double minTouchTarget = 44.0;
  static const double cardCornerRadius = 16.0;
  static const double buttonCornerRadius = 14.0;

  // Apple HIG Typography Scale
  static const TextStyle largeTitle = TextStyle(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.4,
    color: textHighContrast,
  );

  static const TextStyle title1 = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.3,
    color: textHighContrast,
  );

  static const TextStyle title2 = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
    color: textHighContrast,
  );

  static const TextStyle title3 = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    color: textHighContrast,
  );

  static const TextStyle headline = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.4,
    color: textHighContrast,
  );

  static const TextStyle body = TextStyle(
    fontSize: 17,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.4,
    color: textHighContrast,
    height: 1.4,
  );

  static const TextStyle callout = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.3,
    color: textHighContrast,
  );

  static const TextStyle subhead = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.2,
    color: textMuted,
  );

  static const TextStyle footnote = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    letterSpacing: -0.1,
    color: textMuted,
  );

  static const TextStyle caption1 = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.0,
    color: textMuted,
  );

  static const TextStyle caption2 = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
    color: textMuted,
  );

  // HIG Card Decoration with Soft Ambient Shadow
  static BoxDecoration iosCardDecoration({
    Color backgroundColor = darkSurface,
    Color borderColor = cardBorder,
    double radius = cardCornerRadius,
  }) {
    return BoxDecoration(
      color: backgroundColor,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: borderColor, width: 0.8),
      boxShadow: const [
        BoxShadow(
          color: Color(0x08000000),
          blurRadius: 10,
          offset: Offset(0, 3),
        ),
      ],
    );
  }

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: darkCanvas,
      colorScheme: const ColorScheme.light(
        primary: primaryTeal,
        secondary: royalAmethyst,
        surface: darkSurface,
        onSurface: textHighContrast,
        onPrimary: Colors.white,
      ),
      dividerColor: cardBorder,
      cardTheme: CardThemeData(
        color: darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(cardCornerRadius),
          side: const BorderSide(color: cardBorder, width: 0.8),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: title2,
        titleLarge: title3,
        bodyLarge: body,
        bodyMedium: subhead,
      ),
    );
  }
}

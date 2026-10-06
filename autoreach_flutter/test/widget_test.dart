import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:autoreach/screens/login_screen.dart';

void main() {
  testWidgets('login page exposes acceptable-use acceptance control',
      (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));
    expect(find.text('AutoReach'), findsOneWidget);
    expect(find.text('I agree to follow the AutoReach Acceptable Use Policy.'),
        findsOneWidget);
    expect(find.text('Continue with Email'), findsOneWidget);
  });
}

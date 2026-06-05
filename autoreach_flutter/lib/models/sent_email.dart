class SentEmail {
  final String businessName;
  final String email;
  final String subject;
  final String dateSent;

  const SentEmail({required this.businessName, required this.email, required this.subject, required this.dateSent});

  factory SentEmail.fromMap(Map<String, String> map) => SentEmail(
    businessName: map['business_name'] ?? '',
    email:        map['email']         ?? '',
    subject:      map['subject']       ?? '',
    dateSent:     map['date_sent']     ?? '',
  );
}

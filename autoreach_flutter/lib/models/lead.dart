class Lead {
  final String name;
  final String address;
  final String phone;
  final String website;
  final String email;
  final String stage; // New, Contacted, Replied, Closed

  const Lead({
    required this.name,
    required this.address,
    required this.phone,
    required this.website,
    required this.email,
    this.stage = 'New',
  });

  factory Lead.fromMap(Map<String, String> map) => Lead(
    name:    map['name']    ?? '',
    address: map['address'] ?? '',
    phone:   map['phone']   ?? '',
    website: map['website'] ?? '',
    email:   map['email']   ?? '',
    stage:   map['stage']   ?? 'New',
  );

  Lead copyWith({String? name, String? address, String? phone, String? website, String? email, String? stage}) => Lead(
    name:    name    ?? this.name,
    address: address ?? this.address,
    phone:   phone   ?? this.phone,
    website: website ?? this.website,
    email:   email   ?? this.email,
    stage:   stage   ?? this.stage,
  );

  Map<String, String> toMap() => {
    'name': name, 'address': address, 'phone': phone,
    'website': website, 'email': email, 'stage': stage,
  };
}

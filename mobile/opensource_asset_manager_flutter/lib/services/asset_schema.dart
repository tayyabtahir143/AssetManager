class FieldDef {
  final String name;
  final String label;
  const FieldDef(this.name, this.label);
}

class AssetSchema {
  static const Map<String, List<FieldDef>> schemas = {
    'laptops': [
      FieldDef('asset_tag', 'Asset Tag'),
      FieldDef('vendor', 'Vendor'),
      FieldDef('model', 'Model'),
      FieldDef('processor', 'Processor'),
      FieldDef('ram', 'RAM'),
      FieldDef('hard_disk', 'Hard Disk'),
      FieldDef('screen_size', 'Screen size'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'computers': [
      FieldDef('asset_tag', 'Asset Tag'),
      FieldDef('vendor', 'Vendor'),
      FieldDef('model', 'Model'),
      FieldDef('processor', 'Processor'),
      FieldDef('ram', 'RAM'),
      FieldDef('hard_disk', 'Hard Disk'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'screens': [
      FieldDef('asset_tag', 'Asset Tag'),
      FieldDef('vendor', 'Vendor'),
      FieldDef('model', 'Model'),
      FieldDef('size', 'Screen size'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'keyboards': [
      FieldDef('wired', 'Wired'),
      FieldDef('wireless', 'Wireless'),
      FieldDef('model', 'Model'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'mice': [
      FieldDef('connection', 'Connection'),
      FieldDef('model', 'Model'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'headsets': [
      FieldDef('wired', 'Wired'),
      FieldDef('wireless', 'Wireless'),
      FieldDef('model', 'Model'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
    'ram': [
      FieldDef('vendor', 'Vendor'),
      FieldDef('model', 'Model'),
      FieldDef('total_quantity', 'Total Quantity'),
      FieldDef('assigned_quantity', 'Assigned Quantity'),
      FieldDef('dept', 'Dept'),
      FieldDef('assigned_to', 'User'),
      FieldDef('status', 'Status'),
    ],
  };
}

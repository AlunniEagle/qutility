# QUtility - QGIS Plugin

![QGIS Plugin](https://img.shields.io/badge/QGIS-3.28%2B-green)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)

**QUtility** is a comprehensive multifunctional toolbox for QGIS, designed to simplify and speed up everyday vector data management tasks. It provides a unified interface for common GIS operations that would otherwise require multiple tools or complex workflows.

## 🚀 Main Features Overview

QUtility combines 5 powerful tools in a single, user-friendly interface:

### 1. **Field Manager** 🔧
Advanced field management for vector layers with bulk operations support.

### 2. **Layer Renamer** 📝
Batch renaming operations for multiple layers with advanced pattern matching.

### 3. **Layer Loader** 📂
Intelligent layer loading from various sources with filtering capabilities.

### 4. **Feature Excluder** ⚡
Remove duplicate or matching features between layers with geometric and attribute-based filtering.

### 5. **Batch Converter** 🔄
Convert multiple files between different vector formats with coordinate transformation.

### 6. **Overlaps Counter** 📊
Count and analyze overlapping features between line layers.

---

## 🛠️ Detailed Tool Documentation

### 🔧 Field Manager

Modify field properties across multiple vector layers simultaneously.

**Key Features:**
- **Bulk field modifications**: Change field types, lengths, and precision for multiple layers at once
- **Data type conversion**: Convert between String, Integer, and Double with automatic value preservation
- **Field renaming**: Rename fields while maintaining data integrity  
- **Smart validation**: Automatic input validation to prevent data corruption
- **NULL value handling**: Properly handles NULL values during conversions

**Supported Field Types:**
- `String` (with customizable length, default: 255)
- `Integer` (32-bit)
- `Double` (with customizable precision, default: 0)

**Use Cases:**
- Standardize field schemas across multiple datasets
- Convert numeric fields stored as text to proper numeric types
- Prepare data for specific format requirements (e.g., Shapefile limitations)

---

### 📝 Layer Renamer  

Powerful batch renaming system for layers with multiple operation types.

**Available Operations:**
- **Prefix addition**: Add text at the beginning of layer names
- **Suffix addition**: Add text at the end of layer names  
- **Text replacement**: Find and replace specific text patterns
- **Character removal**: Remove N characters from left or right
- **Combined operations**: Apply multiple renaming rules simultaneously

**Features:**
- **Multi-selection support**: Rename multiple layers in one operation
- **Preview system**: See exactly what changes will be applied before confirming
- **Undo-safe**: Uses QGIS's built-in layer management system
- **Smart validation**: Prevents empty names and invalid characters

**Example Use Cases:**
- Add date prefixes to temporal datasets: `2024_` + layer name
- Remove file extensions from imported layer names
- Standardize naming conventions across projects
- Replace underscores with spaces for better readability

---

### 📂 Layer Loader

Advanced layer loading system with comprehensive filtering and organization tools.

**Supported Formats:**
- **Vector**: Shapefile (.shp), GeoPackage (.gpkg), GML (.gml), DBF (.dbf)
- **Raster**: GeoTIFF (.tif)  
- **Tabular**: Excel (.xlsx)
- **Archives**: ZIP, TAR, RAR, 7Z, GZ (with nested archive support)

**Filtering Options:**

**📅 Date Filter**
- Load only files modified after a specific date/time
- Useful for loading recent data updates

**📝 Name Filter**  
- Filter files by name containing specific text
- Case-insensitive matching
- Great for loading files matching naming patterns

**🗺️ Geometry Filter** (Vector files only)
- Filter by geometry type: Point, Line, Polygon, or any
- Automatic geometry type detection
- Multi-geometry support (MultiPoint, MultiLineString, MultiPolygon)

**Advanced Options:**
- **Recursive search**: Scan subfolders for files
- **Nested archive extraction**: Automatically extract and process ZIP files within ZIP files
- **Auto-grouping**: Organize loaded layers in groups based on folder structure
- **Empty group cleanup**: Automatically remove empty groups after loading

**Use Cases:**
- Load all shapefiles from a complex folder structure
- Import only recent survey data based on modification date
- Load specific geometry types for analysis
- Batch import from compressed archives

---

### ⚡ Feature Excluder

Remove duplicate or unwanted features based on attribute and geometric criteria.

**Matching Methods:**

**🔤 Attribute Matching**
- **Join fields**: Match features based on any field values
- **Case sensitivity**: Optional case-sensitive matching
- **NULL handling**: Properly handles NULL values in comparisons

**🗺️ Geometric Comparison**
- **Exact geometry**: Features must have identical geometries
- **Tolerance-based**: Allow small differences (in meters)
- **Spatial relations**: Choose between "Intersects" or "Contains"
- **CRS transformation**: Automatic coordinate system conversion for accurate measurements

**Advanced Options:**
- **Backup creation**: Automatically backup original layers before deletion
- **Interactive selection**: Review and manually select which features to delete
- **Statistics reporting**: Detailed reports on geometry differences
- **Export capabilities**: Export selected features to CSV or create temporary layers

**Selection Tools:**
- Select all/none features
- Filter by geometry status (equal/different)  
- Manual multi-selection
- Export selected features for review

**Use Cases:**
- Remove duplicate features between datasets
- Clean overlapping administrative boundaries
- Eliminate redundant infrastructure features
- Quality control for merged datasets

---

### 🔄 Batch Converter

Convert multiple files between vector formats with coordinate transformation support.

**Supported Formats:**
- **Input/Output**: Shapefile, GeoJSON, GeoPackage, KML, GML, SQLite, CSV, DXF, FileGDB
- **Special handling**: MapInfo TAB format with attribute schema optimization

**Key Features:**

**🌍 Coordinate Transformation**
- **Project CRS integration**: Uses current project CRS as default
- **Custom CRS selection**: Choose any coordinate reference system
- **Automatic validation**: Ensures CRS compatibility

**📋 CSV Export Options**
- **Custom delimiters**: Comma, semicolon, tab, space, colon
- **Encoding support**: UTF-8 encoding for international characters

**📦 GeoPackage Features**
- **Single file option**: Combine multiple inputs into one GeoPackage
- **Layer naming**: Custom naming for internal layers
- **Batch processing**: Individual files or consolidated output

**🛡️ Format-Specific Handling**
- **DXF limitations**: Automatic handling of attribute limitations
- **MapInfo compatibility**: Field type conversion and validation
- **Shapefile constraints**: Automatic field name truncation

**Progress Tracking:**
- **Visual progress**: Real-time progress dialog with file status
- **Error reporting**: Detailed error messages for failed conversions
- **Success statistics**: Summary of conversion results

**Use Cases:**
- Convert legacy MapInfo files to modern formats
- Prepare data for web mapping (GeoJSON)
- Create mobile-friendly datasets (GeoPackage)
- Export data with specific coordinate systems

---

### 📊 Overlaps Counter

Analyze overlapping features between two line layers with detailed reporting.

**Analysis Features:**
- **Spatial overlap detection**: Find where line features intersect or overlap
- **Count quantification**: Calculate exact number of overlaps per feature
- **Statistical reporting**: Generate comprehensive overlap statistics

**Input Options:**
- **Layer selection**: Choose any two line layers from the project
- **Coordinate system**: Requires EPSG:4326 for accurate analysis
- **Selection support**: Process only selected features if needed

**Output Formats:**
- **Shapefile**: Traditional GIS format
- **GeoPackage**: Modern, compact format
- **GeoJSON**: Web-compatible format
- **CSV**: Tabular data for analysis

**Results Include:**
- **Original attributes**: All original layer attributes preserved
- **Overlap count**: New field with number of overlapping features
- **Feature statistics**: Total features processed, overlap summary

**Use Cases:**
- Analyze cable/pipe networks for conflicts
- Count road intersections
- Assess infrastructure overlap density
- Quality control for linear datasets

---

## 🖥️ System Requirements

- **QGIS Version**: 3.28.9 to 3.99 (LTR and current versions)
- **Operating System**: Windows, macOS, Linux
- **Python**: 3.x (included with QGIS)
- **Dependencies**: All dependencies included with standard QGIS installation

## 📦 Installation

### Method 1: QGIS Plugin Repository (Recommended)
1. Open QGIS
2. Go to `Plugins` → `Manage and Install Plugins`
3. Search for "QUtility"
4. Click `Install Plugin`

### Method 2: Manual Installation
1. Download the plugin files:
   ```bash
   git clone https://github.com/AlunniEagle/qutility.git
   ```

2. Copy the plugin folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

3. Restart QGIS and enable the plugin in the Plugin Manager

## 🎯 Quick Start Guide

1. **Launch QUtility**: Find the QUtility icon in your QGIS toolbar or access it via `Plugins` → `QUtility`

2. **Choose Your Tool**: Select from the 6 available tools using the tabs in the dialog

3. **Configure Settings**: Each tool has intuitive controls with helpful tooltips

4. **Preview Changes**: Most tools show you exactly what will happen before making changes

5. **Execute Operations**: Run your operations with detailed progress feedback

## 💡 Tips and Best Practices

### General Tips
- **Always backup your data** before running batch operations
- **Test with a small dataset** first to verify settings
- **Check coordinate systems** match your project requirements
- **Use descriptive naming** for output files and layers

### Performance Optimization
- **Close unnecessary layers** before large batch operations
- **Use filters** to limit processing to relevant features
- **Choose appropriate output formats** for your use case
- **Monitor memory usage** during large operations

### Data Quality
- **Validate geometry** before processing
- **Check for NULL values** in critical fields
- **Verify coordinate systems** match between datasets
- **Review results** using the built-in statistics and reports

## 🐛 Troubleshooting

### Common Issues

**Plugin Not Loading**
- Ensure QGIS version compatibility (3.28.9+)
- Check Python console for error messages
- Verify plugin files are in correct directory

**Processing Errors**
- Check layer validity and geometry
- Ensure adequate disk space for operations
- Verify field names contain only valid characters
- Check coordinate system compatibility

**Performance Issues**
- Close unnecessary applications
- Process data in smaller batches
- Use simpler geometry when possible
- Ensure adequate RAM for large datasets

## 🤝 Contributing

We welcome contributions to QUtility! Here's how you can help:

### Reporting Issues
- Use the [GitHub Issues](https://github.com/AlunniEagle/qutility/issues) page
- Provide detailed descriptions and steps to reproduce
- Include QGIS version and operating system information
- Attach sample data when possible (no sensitive information)

### Contributing Code
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with clear, commented code
4. Test thoroughly with different datasets
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Documentation
- Help improve this README
- Add code comments
- Create video tutorials
- Translate to other languages

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**GIS Team by Eagleprojects S.p.A**
- Email: gis@eagleprojects.it
- Company: [EagleProjects S.p.A.](https://www.eagleprojects.it)
- GitHub: [@AlunniEagle](https://github.com/AlunniEagle)


---

**Made with ❤️ for the QGIS community**

*QUtility - Simplifying GIS workflows, one tool at a time.*

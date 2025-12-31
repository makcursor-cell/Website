"""
Backend parser for *.report.avgpwr files
Generates formatted HTML power dashboards with regex-based parsing
"""

import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json


class PowerReportParser:
    """Regex-based parser for *.report.avgpwr files"""
    
    # Regex patterns for parsing power report files
    PATTERNS = {
        'header': r'^#\s+Power\s+Report\s*$',
        'timestamp': r'Timestamp:\s+(.+?)(?:\s|$)',
        'device_name': r'Device:\s+(.+?)(?:\s|$)',
        'total_power': r'Total\s+Power:\s+(\d+\.?\d*)\s*(mW|W|µW)',
        'cpu_power': r'CPU\s+Power:\s+(\d+\.?\d*)\s*(mW|W|µW)',
        'gpu_power': r'GPU\s+Power:\s+(\d+\.?\d*)\s*(mW|W|µW)',
        'memory_power': r'Memory\s+Power:\s+(\d+\.?\d*)\s*(mW|W|µW)',
        'other_power': r'Other\s+Power:\s+(\d+\.?\d*)\s*(mW|W|µW)',
        'duration': r'Duration:\s+(\d+\.?\d*)\s*(s|ms|µs)',
        'frequency': r'Frequency:\s+(\d+\.?\d*)\s*(MHz|GHz|KHz)',
        'voltage': r'Voltage:\s+(\d+\.?\d*)\s*(V|mV)',
        'temperature': r'Temperature:\s+(\d+\.?\d*)\s*(°C|C|°F|F)',
        'metric_line': r'^(\w+[\w\s]*?):\s+(.+?)$',
    }
    
    def __init__(self):
        """Initialize the parser"""
        self.compiled_patterns = {
            key: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for key, pattern in self.PATTERNS.items()
        }
    
    def is_valid_report_file(self, filepath: str) -> bool:
        """Check if the file is a valid .report.avgpwr file"""
        return filepath.endswith('.report.avgpwr')
    
    def parse_file(self, filepath: str) -> Optional[Dict]:
        """
        Parse a .report.avgpwr file and extract power metrics
        
        Args:
            filepath: Path to the .report.avgpwr file
            
        Returns:
            Dictionary containing parsed metrics or None if parsing fails
        """
        if not self.is_valid_report_file(filepath):
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, OSError) as e:
            print(f"Error reading file {filepath}: {e}")
            return None
        
        return self._parse_content(content, filepath)
    
    def _parse_content(self, content: str, filename: str = '') -> Dict:
        """
        Parse the content of a power report file
        
        Args:
            content: File content as string
            filename: Original filename for reference
            
        Returns:
            Dictionary with parsed metrics
        """
        parsed_data = {
            'filename': filename,
            'parsed_timestamp': datetime.utcnow().isoformat(),
            'metrics': {},
            'raw_metrics': {}
        }
        
        # Parse timestamp
        timestamp_match = self.compiled_patterns['timestamp'].search(content)
        if timestamp_match:
            parsed_data['metrics']['timestamp'] = timestamp_match.group(1)
        
        # Parse device name
        device_match = self.compiled_patterns['device_name'].search(content)
        if device_match:
            parsed_data['metrics']['device_name'] = device_match.group(1)
        
        # Parse power values
        power_fields = ['total_power', 'cpu_power', 'gpu_power', 'memory_power', 'other_power']
        for field in power_fields:
            match = self.compiled_patterns[field].search(content)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                normalized_value = self._normalize_power(value, unit)
                field_name = field.replace('_power', '')
                parsed_data['metrics'][f'{field_name}_power_mw'] = normalized_value
                parsed_data['raw_metrics'][field_name] = {'value': value, 'unit': unit}
        
        # Parse frequency
        freq_match = self.compiled_patterns['frequency'].search(content)
        if freq_match:
            value = float(freq_match.group(1))
            unit = freq_match.group(2)
            normalized_freq = self._normalize_frequency(value, unit)
            parsed_data['metrics']['frequency_mhz'] = normalized_freq
            parsed_data['raw_metrics']['frequency'] = {'value': value, 'unit': unit}
        
        # Parse voltage
        voltage_match = self.compiled_patterns['voltage'].search(content)
        if voltage_match:
            value = float(voltage_match.group(1))
            unit = voltage_match.group(2)
            normalized_voltage = self._normalize_voltage(value, unit)
            parsed_data['metrics']['voltage_v'] = normalized_voltage
            parsed_data['raw_metrics']['voltage'] = {'value': value, 'unit': unit}
        
        # Parse temperature
        temp_match = self.compiled_patterns['temperature'].search(content)
        if temp_match:
            value = float(temp_match.group(1))
            unit = temp_match.group(2)
            parsed_data['metrics']['temperature_c'] = value
            parsed_data['raw_metrics']['temperature'] = {'value': value, 'unit': unit}
        
        # Parse duration
        duration_match = self.compiled_patterns['duration'].search(content)
        if duration_match:
            value = float(duration_match.group(1))
            unit = duration_match.group(2)
            normalized_duration = self._normalize_duration(value, unit)
            parsed_data['metrics']['duration_ms'] = normalized_duration
            parsed_data['raw_metrics']['duration'] = {'value': value, 'unit': unit}
        
        # Parse any additional metric lines
        for line in content.split('\n'):
            metric_match = self.compiled_patterns['metric_line'].match(line.strip())
            if metric_match and not line.strip().startswith('#'):
                key = metric_match.group(1).lower().replace(' ', '_')
                value = metric_match.group(2).strip()
                if key not in parsed_data['metrics']:
                    parsed_data['metrics'][key] = value
        
        return parsed_data
    
    @staticmethod
    def _normalize_power(value: float, unit: str) -> float:
        """Normalize power values to milliwatts"""
        unit = unit.lower()
        if unit == 'w':
            return value * 1000
        elif unit == 'µw':
            return value / 1000
        return value  # Already in mW
    
    @staticmethod
    def _normalize_frequency(value: float, unit: str) -> float:
        """Normalize frequency values to MHz"""
        unit = unit.lower()
        if unit == 'ghz':
            return value * 1000
        elif unit == 'khz':
            return value / 1000
        return value  # Already in MHz
    
    @staticmethod
    def _normalize_voltage(value: float, unit: str) -> float:
        """Normalize voltage values to volts"""
        unit = unit.lower()
        if unit == 'mv':
            return value / 1000
        return value  # Already in V
    
    @staticmethod
    def _normalize_duration(value: float, unit: str) -> float:
        """Normalize duration values to milliseconds"""
        unit = unit.lower()
        if unit == 's':
            return value * 1000
        elif unit == 'µs':
            return value / 1000
        return value  # Already in ms


class HTMLDashboardGenerator:
    """Generate formatted HTML power dashboards from parsed data"""
    
    CSS_TEMPLATE = """
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        
        .dashboard-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .dashboard-title {{
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        
        .dashboard-subtitle {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 8px;
        }}
        
        .dashboard-filename {{
            font-size: 12px;
            opacity: 0.8;
            font-family: 'Monaco', monospace;
        }}
        
        .metrics-container {{
            padding: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }}
        
        .metric-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #555;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        
        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            color: #333;
            margin-bottom: 5px;
        }}
        
        .metric-unit {{
            font-size: 12px;
            color: #888;
            font-weight: 500;
        }}
        
        .power-critical {{
            background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%) !important;
            color: white;
        }}
        
        .power-critical .metric-label {{
            color: rgba(255, 255, 255, 0.9);
        }}
        
        .power-critical .metric-value {{
            color: white;
        }}
        
        .power-critical .metric-unit {{
            color: rgba(255, 255, 255, 0.8);
        }}
        
        .power-warning {{
            background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%) !important;
        }}
        
        .power-normal {{
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%) !important;
        }}
        
        .breakdown-section {{
            padding: 30px;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
        }}
        
        .breakdown-title {{
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 20px;
        }}
        
        .power-breakdown {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        
        .breakdown-item {{
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}
        
        .breakdown-item-label {{
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 5px;
            font-weight: 600;
        }}
        
        .breakdown-item-value {{
            font-size: 20px;
            font-weight: 700;
            color: #333;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: #e9ecef;
            border-radius: 3px;
            margin-top: 8px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 3px;
        }}
        
        .footer {{
            padding: 20px 30px;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
            text-align: center;
            font-size: 12px;
            color: #888;
        }}
        
        @media (max-width: 768px) {{
            .metrics-container {{
                grid-template-columns: 1fr;
            }}
            
            .dashboard-title {{
                font-size: 22px;
            }}
        }}
    </style>
    """
    
    def __init__(self):
        """Initialize the dashboard generator"""
        self.parser = PowerReportParser()
    
    def generate_html_dashboard(self, parsed_data: Dict) -> str:
        """
        Generate an HTML dashboard from parsed power report data
        
        Args:
            parsed_data: Dictionary containing parsed metrics
            
        Returns:
            HTML string for the dashboard
        """
        metrics = parsed_data.get('metrics', {})
        filename = parsed_data.get('filename', 'Unknown')
        
        # Extract key metrics
        total_power = metrics.get('total_power_mw', 0)
        cpu_power = metrics.get('cpu_power_mw', 0)
        gpu_power = metrics.get('gpu_power_mw', 0)
        memory_power = metrics.get('memory_power_mw', 0)
        frequency = metrics.get('frequency_mhz', 0)
        voltage = metrics.get('voltage_v', 0)
        temperature = metrics.get('temperature_c', 0)
        timestamp = metrics.get('timestamp', 'N/A')
        device_name = metrics.get('device_name', 'Unknown Device')
        
        # Determine power level indicator
        power_class = self._get_power_class(total_power)
        
        # Build HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            '    <title>Power Dashboard - {}</title>'.format(Path(filename).stem),
            self.CSS_TEMPLATE,
            '</head>',
            '<body>',
            '    <div class="dashboard">',
            '        <div class="dashboard-header">',
            '            <div class="dashboard-title">⚡ Power Performance Dashboard</div>',
            '            <div class="dashboard-subtitle">Device: {}</div>'.format(device_name),
            '            <div class="dashboard-subtitle">Report Time: {}</div>'.format(timestamp),
            '            <div class="dashboard-filename">Source: {}</div>'.format(Path(filename).name),
            '        </div>',
        ]
        
        # Main metrics section
        html_parts.extend([
            '        <div class="metrics-container">',
            self._build_metric_card('Total Power', total_power, 'mW', power_class),
            self._build_metric_card('CPU Power', cpu_power, 'mW', 'metric-card'),
            self._build_metric_card('GPU Power', gpu_power, 'mW', 'metric-card'),
            self._build_metric_card('Memory Power', memory_power, 'mW', 'metric-card'),
            self._build_metric_card('Frequency', frequency, 'MHz', 'metric-card'),
            self._build_metric_card('Voltage', voltage, 'V', 'metric-card'),
            self._build_metric_card('Temperature', temperature, '°C', 'metric-card'),
            '        </div>',
        ])
        
        # Power breakdown section
        html_parts.extend([
            '        <div class="breakdown-section">',
            '            <div class="breakdown-title">Power Distribution Breakdown</div>',
            '            <div class="power-breakdown">',
            self._build_breakdown_item('CPU', cpu_power, total_power),
            self._build_breakdown_item('GPU', gpu_power, total_power),
            self._build_breakdown_item('Memory', memory_power, total_power),
            '            </div>',
            '        </div>',
        ])
        
        # Footer
        html_parts.extend([
            '        <div class="footer">',
            '            Generated on {} | Power Report Dashboard'.format(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')),
            '        </div>',
            '    </div>',
            '</body>',
            '</html>',
        ])
        
        return '\n'.join(html_parts)
    
    @staticmethod
    def _get_power_class(power_mw: float) -> str:
        """Determine CSS class based on power consumption level"""
        if power_mw > 10000:  # > 10W
            return 'metric-card power-critical'
        elif power_mw > 5000:  # > 5W
            return 'metric-card power-warning'
        return 'metric-card power-normal'
    
    @staticmethod
    def _build_metric_card(label: str, value: float, unit: str, css_class: str) -> str:
        """Build an individual metric card"""
        return (
            f'            <div class="{css_class}">'
            f'                <div class="metric-label">{label}</div>'
            f'                <div class="metric-value">{value:.2f}</div>'
            f'                <div class="metric-unit">{unit}</div>'
            f'            </div>'
        )
    
    @staticmethod
    def _build_breakdown_item(label: str, value: float, total: float) -> str:
        """Build a power breakdown item with progress bar"""
        percentage = (value / total * 100) if total > 0 else 0
        return (
            f'                <div class="breakdown-item">'
            f'                    <div class="breakdown-item-label">{label}</div>'
            f'                    <div class="breakdown-item-value">{value:.2f} mW</div>'
            f'                    <div class="progress-bar">'
            f'                        <div class="progress-fill" style="width: {percentage:.1f}%"></div>'
            f'                    </div>'
            f'                </div>'
        )
    
    def generate_dashboard_from_file(self, filepath: str) -> Optional[str]:
        """
        Generate HTML dashboard directly from a .report.avgpwr file
        
        Args:
            filepath: Path to the .report.avgpwr file
            
        Returns:
            HTML string or None if parsing fails
        """
        parsed_data = self.parser.parse_file(filepath)
        if parsed_data is None:
            return None
        return self.generate_html_dashboard(parsed_data)


def process_power_reports(directory: str, output_directory: str = None) -> Dict[str, str]:
    """
    Process all .report.avgpwr files in a directory and generate HTML dashboards
    
    Args:
        directory: Directory containing .report.avgpwr files
        output_directory: Directory to save generated HTML files (defaults to directory)
        
    Returns:
        Dictionary mapping input filenames to output HTML filenames
    """
    if output_directory is None:
        output_directory = directory
    
    # Create output directory if it doesn't exist
    Path(output_directory).mkdir(parents=True, exist_ok=True)
    
    generator = HTMLDashboardGenerator()
    results = {}
    
    # Find all .report.avgpwr files
    report_files = Path(directory).glob('*.report.avgpwr')
    
    for report_file in report_files:
        print(f"Processing: {report_file.name}")
        
        html_content = generator.generate_dashboard_from_file(str(report_file))
        
        if html_content:
            # Generate output filename
            output_filename = report_file.stem + '.html'
            output_path = Path(output_directory) / output_filename
            
            # Write HTML file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            results[report_file.name] = output_filename
            print(f"  ✓ Generated: {output_filename}")
        else:
            print(f"  ✗ Failed to parse: {report_file.name}")
    
    return results


# CLI Usage
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        
        if os.path.isdir(input_path):
            print(f"Processing directory: {input_path}")
            results = process_power_reports(input_path, output_path)
            print(f"\nSuccessfully processed {len(results)} files")
        elif os.path.isfile(input_path):
            print(f"Processing file: {input_path}")
            generator = HTMLDashboardGenerator()
            html = generator.generate_dashboard_from_file(input_path)
            
            if html:
                output_file = Path(input_path).stem + '.html'
                if output_path:
                    output_file = Path(output_path) / output_file
                
                with open(output_file, 'w') as f:
                    f.write(html)
                print(f"Dashboard saved to: {output_file}")
            else:
                print("Failed to generate dashboard")
        else:
            print(f"Path not found: {input_path}")
    else:
        print("Usage: python backend.py <input_file_or_directory> [output_directory]")
        print("Example: python backend.py report.report.avgpwr .")
        print("Example: python backend.py ./reports ./dashboards")

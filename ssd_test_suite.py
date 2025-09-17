#!/usr/bin/env python3
"""
Enterprise NVMe SSD Test Suite
Comprehensive testing program for NVMe PCIe Gen5 SSDs including:
- System information collection
- Drive formatting options
- Pre-conditioning (random/sequential/mixed)
- Performance testing with FIO
- Data collection and CSV logging
"""

import psutil
import pandas as pd
import subprocess
import datetime
import json
import time
import os
import sys
from pathlib import Path

class SSDTester:
    def __init__(self, verbose=False):
        """Initialize the SSD tester utility class."""
        self.verbose = verbose
        self.csv_file = "ssd_test_results.csv"
        self.csv_columns = [
            'timestamp', 'test_phase', 'drive_model', 'drive_serial', 'drive_firmware', 'drive_capacity_gb',
            'smart_critical_warning', 'smart_temperature_c', 'smart_available_spare_pct', 'smart_percentage_used',
            'error_count_media', 'error_count_correctable', 'pcie_link_speed', 'pcie_link_width',
            'cpu_model', 'cpu_cores', 'total_memory_gb', 'disk_count', 'test_duration_seconds',
            'iops_read', 'iops_write', 'latency_read_us', 'latency_write_us', 'bandwidth_read_mbps', 'bandwidth_write_mbps'
        ]
        
        # Data members to store all collected information
        self.system_info = {}
        self.nvme_drives = []
        self.selected_device = None
        self.smart_data = {}  # device -> smart data mapping
        self.error_data = {}  # device -> error data mapping
        self.pcie_data = {}
        self.format_results = {}  # device -> format results
        self.preconditioning_results = {}  # device -> precond results
        self.performance_results = {}  # device -> performance results
        self.test_history = []  # chronological list of all operations
        
        if self.verbose:
            print("=== Enterprise NVMe SSD Test Suite (Utility Class) ===")
            print("Initialized successfully.")
    
    
    def check_dependencies(self):
        """Check if required system tools are available."""
        required_tools = ['nvme', 'fio', 'lspci', 'sensors', 'parted']
        missing_tools = []
        
        for tool in required_tools:
            try:
                subprocess.run([tool, '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    subprocess.run([tool, '--help'], capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    missing_tools.append(tool)
        
        if missing_tools:
            print(f"ERROR: Missing required tools: {', '.join(missing_tools)}")
            print("Please install:")
            for tool in missing_tools:
                if tool == 'nvme':
                    print("  - nvme-cli package")
                elif tool == 'fio':
                    print("  - fio package")
                elif tool == 'sensors':
                    print("  - lm-sensors package")
                else:
                    print(f"  - {tool} package")
            return False
        
        if self.verbose:
            print("All required tools are available.")
        return True
    
    def select_device(self, device):
        """Select a device for testing operations."""
        self.selected_device = device
        self._add_to_history('device_selection', {'device': device})
        if self.verbose:
            print(f"Selected device: {device}")
    
    def get_system_info(self):
        """Get collected system information."""
        return self.system_info.copy()
    
    def get_smart_data(self, device=None):
        """Get SMART data for device or all devices."""
        if device:
            return self.smart_data.get(device, {})
        return self.smart_data.copy()
    
    def get_performance_results(self, device=None):
        """Get performance test results for device or all devices."""
        if device:
            return self.performance_results.get(device, {})
        return self.performance_results.copy()
    
    def get_all_data_for_device(self, device):
        """Get all collected data for a specific device."""
        return {
            'device': device,
            'smart_data': self.smart_data.get(device, {}),
            'error_data': self.error_data.get(device, {}),
            'format_results': self.format_results.get(device, {}),
            'preconditioning_results': self.preconditioning_results.get(device, {}),
            'performance_results': self.performance_results.get(device, {})
        }
    
    def export_all_data(self):
        """Export all collected data as a comprehensive dictionary."""
        return {
            'system_info': self.system_info,
            'nvme_drives': self.nvme_drives,
            'selected_device': self.selected_device,
            'smart_data': self.smart_data,
            'error_data': self.error_data,
            'pcie_data': self.pcie_data,
            'format_results': self.format_results,
            'preconditioning_results': self.preconditioning_results,
            'performance_results': self.performance_results,
            'test_history': self.test_history
        }
    
    def collect_all_device_data(self, device):
        """Convenience method to collect all data for a device."""
        self.collect_nvme_smart(device)
        self.collect_nvme_errors(device)
        self.collect_pcie_info()
        if self.verbose:
            print(f"Collected all data for device: {device}")
    
    def detect_nvme_drives(self):
        """Detect and list available NVMe drives. Stores results in self.nvme_drives."""
        try:
            result = subprocess.run(['nvme', 'list', '--output-format=json'], 
                                  capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            drives = []
            if 'Devices' in data:
                for device in data['Devices']:
                    drives.append({
                        'device': device.get('DevicePath', 'Unknown'),
                        'model': device.get('ModelNumber', 'Unknown').strip(),
                        'serial': device.get('SerialNumber', 'Unknown').strip(),
                        'size': device.get('PhysicalSize', 0),
                        'firmware': device.get('Firmware', 'Unknown').strip()
                    })
            
            self.nvme_drives = drives
            self._add_to_history('drive_detection', {'drives_found': len(drives), 'drives': drives})
            return drives
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            if self.verbose:
                print(f"Error detecting NVMe drives: {e}")
            self.nvme_drives = []
            return []
    
    def collect_system_info(self):
        """Collect comprehensive system information. Stores results in self.system_info."""
        system_info = {}
        
        try:
            # CPU information
            cpu_info = psutil.cpu_count(logical=False)
            system_info['cpu_cores'] = cpu_info
            
            # Get CPU model
            try:
                lscpu_result = subprocess.run(['lscpu'], capture_output=True, text=True, check=True)
                for line in lscpu_result.stdout.split('\n'):
                    if 'Model name:' in line:
                        system_info['cpu_model'] = line.split(':', 1)[1].strip()
                        break
                else:
                    system_info['cpu_model'] = 'Unknown'
            except subprocess.CalledProcessError:
                system_info['cpu_model'] = 'Unknown'
            
            # Memory information
            memory = psutil.virtual_memory()
            system_info['total_memory_gb'] = round(memory.total / (1024**3), 2)
            
            # Disk count
            system_info['disk_count'] = len(psutil.disk_partitions())
            
            # Current timestamp
            system_info['timestamp'] = datetime.datetime.now().isoformat()
            
        except Exception as e:
            if self.verbose:
                print(f"Error collecting system info: {e}")
            system_info = {
                'cpu_cores': 0,
                'cpu_model': 'Unknown',
                'total_memory_gb': 0,
                'disk_count': 0,
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        self.system_info = system_info
        self._add_to_history('system_info_collection', system_info)
        return system_info
    
    def collect_nvme_smart(self, device):
        """Collect NVMe SMART data. Stores results in self.smart_data[device]."""
        smart_data = {}
        
        try:
            result = subprocess.run(['nvme', 'smart-log', device, '--output-format=json'], 
                                  capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            smart_data = {
                'critical_warning': data.get('critical_warning', 0),
                'temperature_c': data.get('temperature', 0),
                'available_spare_pct': data.get('avail_spare', 0),
                'percentage_used': data.get('percent_used', 0)
            }
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            if self.verbose:
                print(f"Error collecting SMART data for {device}: {e}")
            smart_data = {
                'critical_warning': 0,
                'temperature_c': 0,
                'available_spare_pct': 0,
                'percentage_used': 0
            }
        
        self.smart_data[device] = smart_data
        self._add_to_history('smart_data_collection', {'device': device, 'smart_data': smart_data})
        return smart_data
    
    def collect_nvme_errors(self, device):
        """Collect NVMe error log data. Stores results in self.error_data[device]."""
        error_data = {}
        
        try:
            result = subprocess.run(['nvme', 'error-log', device, '--output-format=json'], 
                                  capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            media_errors = 0
            correctable_errors = 0
            
            if isinstance(data, list):
                for error in data:
                    error_info = error.get('error_information', 0)
                    if error_info & 0x1:  # Media error bit
                        media_errors += 1
                    if error_info & 0x2:  # Correctable error bit
                        correctable_errors += 1
            
            error_data = {
                'media_errors': media_errors,
                'correctable_errors': correctable_errors
            }
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            if self.verbose:
                print(f"Error collecting error log for {device}: {e}")
            error_data = {
                'media_errors': 0,
                'correctable_errors': 0
            }
        
        self.error_data[device] = error_data
        self._add_to_history('error_data_collection', {'device': device, 'error_data': error_data})
        return error_data
    
    def collect_pcie_info(self, device):
        """Collect PCIe link information."""
        pcie_info = {}
        
        try:
            # Get PCIe information
            result = subprocess.run(['lspci', '-vvv'], capture_output=True, text=True, check=True)
            
            # Parse for NVMe controller information
            lines = result.stdout.split('\n')
            in_nvme_section = False
            
            for line in lines:
                if 'NVMe' in line and 'controller' in line.lower():
                    in_nvme_section = True
                elif in_nvme_section and line.startswith('\t'):
                    if 'LnkSta:' in line:
                        # Parse link status
                        if 'Speed' in line:
                            speed_match = line.split('Speed ')[1].split(',')[0] if 'Speed ' in line else 'Unknown'
                            pcie_info['link_speed'] = speed_match
                        if 'Width' in line:
                            width_match = line.split('Width ')[1].split(',')[0] if 'Width ' in line else 'Unknown'
                            pcie_info['link_width'] = width_match
                        break
                elif in_nvme_section and not line.startswith('\t'):
                    break
            
            if 'link_speed' not in pcie_info:
                pcie_info['link_speed'] = 'Unknown'
            if 'link_width' not in pcie_info:
                pcie_info['link_width'] = 'Unknown'
                
        except subprocess.CalledProcessError as e:
            if self.verbose:
                print(f"Error collecting PCIe info: {e}")
            pcie_info = {
                'link_speed': 'Unknown',
                'link_width': 'Unknown'
            }
        
        self.pcie_data = pcie_info
        self._add_to_history('pcie_info_collection', pcie_info)
        return pcie_info
    
    def format_drive(self, device, format_type='quick', confirm=False):
        """Format drive with specified type. Stores results in self.format_results[device].
        
        Args:
            device: Device path (e.g., '/dev/nvme0n1')
            format_type: 'quick', 'full', or 'secure'
            confirm: Must be True for destructive operations
        """
        if not confirm:
            raise ValueError("Destructive format operation requires explicit confirmation (confirm=True)")
        
        start_time = time.time()
        result = {
            'device': device,
            'format_type': format_type,
            'start_time': datetime.datetime.now().isoformat(),
            'success': False,
            'error': None,
            'duration_seconds': 0
        }
        
        if self.verbose:
            print(f"Starting {format_type} format for device: {device}")
        
        try:
            if format_type == 'quick':
                # Quick format - GPT partition table
                subprocess.run(['parted', device, 'mklabel', 'gpt'], check=True)
                if self.verbose:
                    print("Quick format completed.")
                
            elif format_type == 'full':
                # Full format with verification
                subprocess.run(['parted', device, 'mklabel', 'gpt'], check=True)
                subprocess.run(['parted', device, 'mkpart', 'primary', '0%', '100%'], check=True)
                partition = device + 'p1' if 'nvme' in device else device + '1'
                subprocess.run(['mkfs.ext4', '-F', partition], check=True)
                subprocess.run(['e2fsck', '-f', partition], check=True)
                if self.verbose:
                    print("Full format and verification completed.")
                
            elif format_type == 'secure':
                # NVMe secure erase
                subprocess.run(['nvme', 'format', device, '--ses=1'], check=True)
                if self.verbose:
                    print("NVMe secure erase completed.")
            else:
                raise ValueError(f"Invalid format_type: {format_type}. Use 'quick', 'full', or 'secure'")
            
            result['success'] = True
            
        except subprocess.CalledProcessError as e:
            result['error'] = str(e)
            if self.verbose:
                print(f"Format operation failed: {e}")
        
        result['duration_seconds'] = time.time() - start_time
        self.format_results[device] = result
        self._add_to_history('format_operation', result)
        return result['success']
    
    def display_progress(self, current, total, prefix="Progress"):
        """Display progress bar."""
        percent = (current / total) * 100
        bar_length = 50
        filled_length = int(bar_length * current // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        print(f'\r{prefix}: |{bar}| {percent:.1f}%', end='', flush=True)
    
    def run_preconditioning(self, device, precond_type='random'):
        """Run pre-conditioning on device. Stores results in self.preconditioning_results[device].
        
        Args:
            device: Device path (e.g., '/dev/nvme0n1')
            precond_type: 'random', 'sequential', or 'mixed'
        """
        start_time = time.time()
        result = {
            'device': device,
            'precond_type': precond_type,
            'start_time': datetime.datetime.now().isoformat(),
            'success': False,
            'error': None,
            'duration_seconds': 0,
            'fio_results': {}
        }
        
        # Get drive capacity for calculating loops
        try:
            capacity_result = subprocess.run(['nvme', 'id-ctrl', device, '--output-format=json'], 
                                  capture_output=True, text=True, check=True)
            ctrl_data = json.loads(capacity_result.stdout)
            if self.verbose:
                print("Drive capacity detected. Starting pre-conditioning...")
        except:
            if self.verbose:
                print("Warning: Could not detect drive capacity. Using default settings.")
        
        if self.verbose:
            print(f"Starting {precond_type} pre-conditioning on {device}...")
        
        try:
            if precond_type == 'random':
                # 4KB Random Write
                cmd = ['fio', '--name=precond_random', f'--filename={device}', '--rw=randwrite', 
                      '--bs=4k', '--iodepth=32', '--size=100%', '--loops=2', '--output-format=json']
                
            elif precond_type == 'sequential':
                # Sequential Write
                cmd = ['fio', '--name=precond_sequential', f'--filename={device}', '--rw=write',
                      '--bs=1M', '--iodepth=4', '--size=100%', '--loops=2', '--output-format=json']
                
            elif precond_type == 'mixed':
                # Mixed Workload
                cmd = ['fio', '--name=precond_mixed', f'--filename={device}', '--rw=randrw',
                      '--rwmixwrite=70', '--bs=4k', '--iodepth=32', '--size=100%', '--loops=2', '--output-format=json']
            else:
                raise ValueError(f"Invalid precond_type: {precond_type}. Use 'random', 'sequential', or 'mixed'")
            
            if self.verbose:
                print(f"Running command: {' '.join(cmd)}")
            fio_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse FIO results
            try:
                fio_data = json.loads(fio_result.stdout)
                result['fio_results'] = fio_data
            except json.JSONDecodeError:
                result['fio_results'] = {'raw_output': fio_result.stdout}
            
            result['success'] = True
            duration = time.time() - start_time
            
            if self.verbose:
                print(f"Pre-conditioning completed in {duration:.1f} seconds.")
            
        except subprocess.CalledProcessError as e:
            result['error'] = str(e)
            if self.verbose:
                print(f"Pre-conditioning failed: {e}")
        
        result['duration_seconds'] = time.time() - start_time
        self.preconditioning_results[device] = result
        self._add_to_history('preconditioning', result)
        return result['success']
    
    def run_fio_tests(self, device, test_types=['randread']):
        """Run FIO performance tests. Stores results in self.performance_results[device].
        
        Args:
            device: Device path (e.g., '/dev/nvme0n1')
            test_types: List of test types - 'randread', 'randwrite', 'seqread', 'seqwrite', 'mixed', 'qd_scaling'
        """
        start_time = time.time()
        results = {
            'device': device,
            'start_time': datetime.datetime.now().isoformat(),
            'test_types': test_types,
            'tests': {},
            'duration_seconds': 0
        }
        
        if self.verbose:
            print(f"Running FIO performance tests on {device}: {test_types}")
        
        for test_type in test_types:
            if self.verbose:
                print(f"Running {test_type} test...")
            
            try:
                if test_type == 'randread':
                    cmd = ['fio', '--name=randread_4k', f'--filename={device}', '--rw=randread',
                          '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_type == 'randwrite':
                    cmd = ['fio', '--name=randwrite_4k', f'--filename={device}', '--rw=randwrite',
                          '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_type == 'seqread':
                    cmd = ['fio', '--name=seqread_1m', f'--filename={device}', '--rw=read',
                          '--bs=1M', '--iodepth=4', '--runtime=60', '--output-format=json']
                    
                elif test_type == 'seqwrite':
                    cmd = ['fio', '--name=seqwrite_1m', f'--filename={device}', '--rw=write',
                          '--bs=1M', '--iodepth=4', '--runtime=60', '--output-format=json']
                    
                elif test_type == 'mixed':
                    cmd = ['fio', '--name=mixed_7030', f'--filename={device}', '--rw=randrw',
                          '--rwmixread=70', '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_type == 'qd_scaling':
                    # Queue depth scaling
                    qd_results = {}
                    for qd in [1, 4, 8, 16, 32, 64]:
                        if self.verbose:
                            print(f"  Testing queue depth {qd}...")
                        qd_cmd = ['fio', f'--name=qd_{qd}', f'--filename={device}', '--rw=randread',
                                 '--bs=4k', f'--iodepth={qd}', '--runtime=30', '--output-format=json']
                        qd_result = subprocess.run(qd_cmd, capture_output=True, text=True, check=True)
                        qd_data = json.loads(qd_result.stdout)
                        if 'jobs' in qd_data and len(qd_data['jobs']) > 0:
                            job = qd_data['jobs'][0]
                            iops = job.get('read', {}).get('iops', 0)
                            qd_results[f'qd_{qd}'] = {'iops': iops, 'raw_data': qd_data}
                    results['tests'][test_type] = qd_results
                    continue
                else:
                    if self.verbose:
                        print(f"Unknown test type: {test_type}")
                    continue
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                data = json.loads(result.stdout)
                
                # Parse FIO results
                parsed_result = {'raw_data': data}
                if 'jobs' in data and len(data['jobs']) > 0:
                    job = data['jobs'][0]
                    
                    read_data = job.get('read', {})
                    write_data = job.get('write', {})
                    
                    parsed_result.update({
                        'iops_read': read_data.get('iops', 0),
                        'iops_write': write_data.get('iops', 0),
                        'bandwidth_read_mbps': read_data.get('bw', 0) / 1024,  # Convert KB/s to MB/s
                        'bandwidth_write_mbps': write_data.get('bw', 0) / 1024,
                        'latency_read_us': read_data.get('lat_ns', {}).get('mean', 0) / 1000,  # Convert ns to us
                        'latency_write_us': write_data.get('lat_ns', {}).get('mean', 0) / 1000
                    })
                
                results['tests'][test_type] = parsed_result
                
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                if self.verbose:
                    print(f"Test {test_type} failed: {e}")
                results['tests'][test_type] = {
                    'error': str(e),
                    'iops_read': 0, 'iops_write': 0,
                    'bandwidth_read_mbps': 0, 'bandwidth_write_mbps': 0,
                    'latency_read_us': 0, 'latency_write_us': 0
                }
        
        results['duration_seconds'] = time.time() - start_time
        self.performance_results[device] = results
        self._add_to_history('performance_testing', results)
        return results
    
    def _add_to_history(self, operation_type, data):
        """Add operation to test history."""
        history_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'operation_type': operation_type,
            'data': data
        }
        self.test_history.append(history_entry)
    
    def save_to_csv(self, filename=None):
        """Export all collected data to CSV file."""
        if filename is None:
            filename = self.csv_file
        
        try:
            # Flatten test history into CSV-compatible format
            rows = []
            for entry in self.test_history:
                row = {
                    'timestamp': entry['timestamp'],
                    'test_phase': entry['operation_type']
                }
                # Add other columns with default values
                for col in self.csv_columns:
                    if col not in row:
                        row[col] = ''
                
                # Try to populate from data if available
                data = entry.get('data', {})
                for col in self.csv_columns:
                    if col in data:
                        row[col] = data[col]
                
                rows.append(row)
            
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(filename, index=False)
                if self.verbose:
                    print(f"Data exported to {filename}")
                return True
            else:
                if self.verbose:
                    print("No data to export")
                return False
            
        except Exception as e:
            if self.verbose:
                print(f"Error exporting to CSV: {e}")
            return False
    

def main():
    """Example usage of the SSDTester utility class."""
    print("=== SSD Tester Utility Class Example ===")
    print("\nCreating SSDTester instance...")
    tester = SSDTester(verbose=True)
    
    print("\n1. Collecting system information...")
    system_info = tester.collect_system_info()
    print(f"System: {system_info.get('cpu_model', 'Unknown')} with {system_info.get('cpu_cores', 0)} cores")
    
    print("\n2. Detecting NVMe drives...")
    drives = tester.detect_nvme_drives()
    if drives:
        print(f"Found {len(drives)} NVMe drive(s):")
        for drive in drives:
            size_gb = drive['size'] / (1024**3) if drive['size'] > 0 else 0
            print(f"  - {drive['device']}: {drive['model']} ({size_gb:.1f} GB)")
        
        # Select first drive for example
        first_drive = drives[0]['device']
        print(f"\n3. Selecting device: {first_drive}")
        tester.select_device(first_drive)
        
        print("\n4. Collecting device data...")
        tester.collect_all_device_data(first_drive)
        
        print("\n5. Exporting all data...")
        all_data = tester.export_all_data()
        print(f"Collected data for {len(all_data.get('smart_data', {}))} devices")
        
        print("\n6. Saving to CSV...")
        tester.save_to_csv()
        
        print("\nExample completed. Use the class methods programmatically for testing.")
        print("\nAvailable methods:")
        print("  - tester.format_drive(device, format_type, confirm=True)")
        print("  - tester.run_preconditioning(device, precond_type)")
        print("  - tester.run_fio_tests(device, test_types)")
        print("  - tester.export_all_data()")
    else:
        print("No NVMe drives found.")

if __name__ == "__main__":
    # Check for root privileges if running interactively
    if os.geteuid() != 0:
        print("WARNING: This program typically requires root privileges for device access.")
        print("Some operations may fail without sudo.")
        print("Run with: sudo python3 ssd_test_suite.py")
        print()
    
    main()
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
import signal
from pathlib import Path

class SSDTester:
    def __init__(self):
        """Initialize the SSD tester with CSV logging and safety checks."""
        self.csv_file = "ssd_test_results.csv"
        self.csv_columns = [
            'timestamp', 'test_phase', 'drive_model', 'drive_serial', 'drive_firmware', 'drive_capacity_gb',
            'smart_critical_warning', 'smart_temperature_c', 'smart_available_spare_pct', 'smart_percentage_used',
            'error_count_media', 'error_count_correctable', 'pcie_link_speed', 'pcie_link_width',
            'cpu_model', 'cpu_cores', 'total_memory_gb', 'disk_count', 'test_duration_seconds',
            'iops_read', 'iops_write', 'latency_read_us', 'latency_write_us', 'bandwidth_read_mbps', 'bandwidth_write_mbps'
        ]
        
        # Check root privileges
        if os.geteuid() != 0:
            print("ERROR: This program requires root privileges. Please run with sudo.")
            sys.exit(1)
            
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("=== Enterprise NVMe SSD Test Suite ===")
        print("Initializing...")
        
        # Check dependencies
        if not self.check_dependencies():
            sys.exit(1)
    
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\nReceived interrupt signal. Shutting down gracefully...")
        sys.exit(0)
    
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
        
        print("All required tools are available.")
        return True
    
    def detect_nvme_drives(self):
        """Detect and list available NVMe drives."""
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
            
            return drives
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            print(f"Error detecting NVMe drives: {e}")
            return []
    
    def collect_system_info(self):
        """Collect comprehensive system information."""
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
            print(f"Error collecting system info: {e}")
            system_info = {
                'cpu_cores': 0,
                'cpu_model': 'Unknown',
                'total_memory_gb': 0,
                'disk_count': 0,
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        return system_info
    
    def collect_nvme_smart(self, device):
        """Collect NVMe SMART data."""
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
            print(f"Error collecting SMART data for {device}: {e}")
            smart_data = {
                'critical_warning': 0,
                'temperature_c': 0,
                'available_spare_pct': 0,
                'percentage_used': 0
            }
        
        return smart_data
    
    def collect_nvme_errors(self, device):
        """Collect NVMe error log data."""
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
            print(f"Error collecting error log for {device}: {e}")
            error_data = {
                'media_errors': 0,
                'correctable_errors': 0
            }
        
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
            print(f"Error collecting PCIe info: {e}")
            pcie_info = {
                'link_speed': 'Unknown',
                'link_width': 'Unknown'
            }
        
        return pcie_info
    
    def format_drive_menu(self, device):
        """Interactive menu for drive formatting options."""
        print(f"\n=== Format Drive: {device} ===")
        print("WARNING: This will DESTROY ALL DATA on the drive!")
        print("\nFormat Options:")
        print("1. Quick Format (GPT partition table only)")
        print("2. Full Format + Verification")
        print("3. NVMe Secure Erase (sanitize)")
        print("4. Cancel")
        
        choice = input("\nSelect format option (1-4): ").strip()
        
        if choice == '4':
            return False
        
        # Triple confirmation for destructive operations
        print(f"\nYou selected option {choice} for device {device}")
        confirm1 = input("Type 'yes' to confirm this will DESTROY ALL DATA: ").strip().lower()
        if confirm1 != 'yes':
            print("Operation cancelled.")
            return False
        
        confirm2 = input("Type 'DESTROY' to confirm data destruction: ").strip()
        if confirm2 != 'DESTROY':
            print("Operation cancelled.")
            return False
        
        confirm3 = input(f"Type the device name '{device}' to confirm: ").strip()
        if confirm3 != device:
            print("Operation cancelled.")
            return False
        
        print(f"\nProceeding with format option {choice}...")
        
        try:
            if choice == '1':
                # Quick format - GPT partition table
                subprocess.run(['parted', device, 'mklabel', 'gpt'], check=True)
                print("Quick format completed.")
                
            elif choice == '2':
                # Full format with verification
                subprocess.run(['parted', device, 'mklabel', 'gpt'], check=True)
                subprocess.run(['parted', device, 'mkpart', 'primary', '0%', '100%'], check=True)
                partition = device + 'p1' if 'nvme' in device else device + '1'
                subprocess.run(['mkfs.ext4', '-F', partition], check=True)
                subprocess.run(['e2fsck', '-f', partition], check=True)
                print("Full format and verification completed.")
                
            elif choice == '3':
                # NVMe secure erase
                subprocess.run(['nvme', 'format', device, '--ses=1'], check=True)
                print("NVMe secure erase completed.")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Format operation failed: {e}")
            return False
    
    def display_progress(self, current, total, prefix="Progress"):
        """Display progress bar."""
        percent = (current / total) * 100
        bar_length = 50
        filled_length = int(bar_length * current // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        print(f'\r{prefix}: |{bar}| {percent:.1f}%', end='', flush=True)
    
    def run_preconditioning_menu(self, device):
        """Interactive menu for pre-conditioning options."""
        print(f"\n=== Pre-conditioning: {device} ===")
        print("Pre-conditioning Options:")
        print("1. 4KB Random Write (Enterprise Standard)")
        print("2. Sequential Write")
        print("3. Mixed Workload (70% write, 30% read)")
        print("4. Cancel")
        
        choice = input("\nSelect pre-conditioning option (1-4): ").strip()
        
        if choice == '4':
            return False
        
        # Get drive capacity for calculating loops
        try:
            result = subprocess.run(['nvme', 'id-ctrl', device, '--output-format=json'], 
                                  capture_output=True, text=True, check=True)
            ctrl_data = json.loads(result.stdout)
            # This is simplified - in reality you'd need more complex capacity calculation
            print("Drive capacity detected. Starting pre-conditioning...")
        except:
            print("Warning: Could not detect drive capacity. Using default settings.")
        
        print(f"\nStarting pre-conditioning option {choice}...")
        print("This will take several hours. Press Ctrl+C to abort.")
        
        start_time = time.time()
        
        try:
            if choice == '1':
                # 4KB Random Write
                cmd = ['fio', '--name=precond_random', f'--filename={device}', '--rw=randwrite', 
                      '--bs=4k', '--iodepth=32', '--size=100%', '--loops=2', '--output-format=json']
                
            elif choice == '2':
                # Sequential Write
                cmd = ['fio', '--name=precond_sequential', f'--filename={device}', '--rw=write',
                      '--bs=1M', '--iodepth=4', '--size=100%', '--loops=2', '--output-format=json']
                
            elif choice == '3':
                # Mixed Workload
                cmd = ['fio', '--name=precond_mixed', f'--filename={device}', '--rw=randrw',
                      '--rwmixwrite=70', '--bs=4k', '--iodepth=32', '--size=100%', '--loops=2', '--output-format=json']
            
            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\nPre-conditioning completed in {duration:.1f} seconds.")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Pre-conditioning failed: {e}")
            return False
    
    def run_fio_tests_menu(self, device):
        """Interactive menu for FIO performance tests."""
        print(f"\n=== Performance Testing: {device} ===")
        print("Performance Test Options:")
        print("1. 4KB Random Read IOPS")
        print("2. 4KB Random Write IOPS")
        print("3. Sequential Read Bandwidth")
        print("4. Sequential Write Bandwidth")
        print("5. Mixed 70/30 Read/Write")
        print("6. Queue Depth Scaling Test")
        print("7. Run All Tests")
        print("8. Cancel")
        
        choice = input("\nSelect test option (1-8): ").strip()
        
        if choice == '8':
            return {}
        
        results = {}
        
        if choice == '7':
            # Run all tests
            test_choices = ['1', '2', '3', '4', '5', '6']
        else:
            test_choices = [choice]
        
        for test_choice in test_choices:
            print(f"\nRunning test {test_choice}...")
            
            try:
                if test_choice == '1':
                    # 4KB Random Read
                    cmd = ['fio', '--name=randread_4k', f'--filename={device}', '--rw=randread',
                          '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_choice == '2':
                    # 4KB Random Write
                    cmd = ['fio', '--name=randwrite_4k', f'--filename={device}', '--rw=randwrite',
                          '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_choice == '3':
                    # Sequential Read
                    cmd = ['fio', '--name=seqread_1m', f'--filename={device}', '--rw=read',
                          '--bs=1M', '--iodepth=4', '--runtime=60', '--output-format=json']
                    
                elif test_choice == '4':
                    # Sequential Write
                    cmd = ['fio', '--name=seqwrite_1m', f'--filename={device}', '--rw=write',
                          '--bs=1M', '--iodepth=4', '--runtime=60', '--output-format=json']
                    
                elif test_choice == '5':
                    # Mixed workload
                    cmd = ['fio', '--name=mixed_7030', f'--filename={device}', '--rw=randrw',
                          '--rwmixread=70', '--bs=4k', '--iodepth=32', '--runtime=60', '--output-format=json']
                    
                elif test_choice == '6':
                    # Queue depth scaling
                    for qd in [1, 4, 8, 16, 32, 64]:
                        print(f"  Testing queue depth {qd}...")
                        qd_cmd = ['fio', f'--name=qd_{qd}', f'--filename={device}', '--rw=randread',
                                 '--bs=4k', f'--iodepth={qd}', '--runtime=30', '--output-format=json']
                        qd_result = subprocess.run(qd_cmd, capture_output=True, text=True, check=True)
                        qd_data = json.loads(qd_result.stdout)
                        if 'jobs' in qd_data and len(qd_data['jobs']) > 0:
                            job = qd_data['jobs'][0]
                            iops = job.get('read', {}).get('iops', 0)
                            results[f'qd_{qd}_iops'] = iops
                    continue
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                data = json.loads(result.stdout)
                
                # Parse FIO results
                if 'jobs' in data and len(data['jobs']) > 0:
                    job = data['jobs'][0]
                    
                    read_data = job.get('read', {})
                    write_data = job.get('write', {})
                    
                    results[f'test_{test_choice}'] = {
                        'iops_read': read_data.get('iops', 0),
                        'iops_write': write_data.get('iops', 0),
                        'bandwidth_read_mbps': read_data.get('bw', 0) / 1024,  # Convert KB/s to MB/s
                        'bandwidth_write_mbps': write_data.get('bw', 0) / 1024,
                        'latency_read_us': read_data.get('lat_ns', {}).get('mean', 0) / 1000,  # Convert ns to us
                        'latency_write_us': write_data.get('lat_ns', {}).get('mean', 0) / 1000
                    }
                
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                print(f"Test {test_choice} failed: {e}")
                results[f'test_{test_choice}'] = {
                    'iops_read': 0, 'iops_write': 0,
                    'bandwidth_read_mbps': 0, 'bandwidth_write_mbps': 0,
                    'latency_read_us': 0, 'latency_write_us': 0
                }
        
        return results
    
    def log_to_csv(self, data, test_phase="unknown"):
        """Log data to CSV file."""
        try:
            # Create DataFrame with single row
            df_data = {col: [data.get(col, '')] for col in self.csv_columns}
            df_data['test_phase'] = [test_phase]
            df_data['timestamp'] = [datetime.datetime.now().isoformat()]
            
            df = pd.DataFrame(df_data)
            
            # Check if file exists
            if os.path.exists(self.csv_file):
                # Append to existing file
                df.to_csv(self.csv_file, mode='a', header=False, index=False)
            else:
                # Create new file with headers
                df.to_csv(self.csv_file, mode='w', header=True, index=False)
            
            print(f"Data logged to {self.csv_file}")
            
        except Exception as e:
            print(f"Error logging to CSV: {e}")
    
    def main_menu(self):
        """Main interactive menu."""
        selected_device = None
        
        while True:
            print(f"\n{'='*50}")
            print("=== Enterprise NVMe SSD Test Suite ===")
            print(f"{'='*50}")
            
            if selected_device:
                print(f"Selected Device: {selected_device}")
            
            print("\nMenu Options:")
            print("1. System Information & Drive Detection")
            print("2. Format Target Drive")
            print("3. Pre-conditioning")
            print("4. Performance Testing (FIO)")
            print("5. Post-Test Data Collection")
            print("6. Generate Report")
            print("7. Exit")
            
            choice = input("\nSelect option (1-7): ").strip()
            
            if choice == '1':
                # System information and drive detection
                print("\n=== System Information ===")
                system_info = self.collect_system_info()
                
                print(f"CPU: {system_info['cpu_model']}")
                print(f"CPU Cores: {system_info['cpu_cores']}")
                print(f"Total Memory: {system_info['total_memory_gb']} GB")
                print(f"Disk Count: {system_info['disk_count']}")
                print(f"Timestamp: {system_info['timestamp']}")
                
                print("\n=== Available NVMe Drives ===")
                drives = self.detect_nvme_drives()
                
                if not drives:
                    print("No NVMe drives detected.")
                else:
                    for i, drive in enumerate(drives, 1):
                        size_gb = drive['size'] / (1024**3) if drive['size'] > 0 else 0
                        print(f"{i}. {drive['device']}")
                        print(f"   Model: {drive['model']}")
                        print(f"   Serial: {drive['serial']}")
                        print(f"   Size: {size_gb:.1f} GB")
                        print(f"   Firmware: {drive['firmware']}")
                        print()
                    
                    # Drive selection
                    if len(drives) > 0:
                        try:
                            selection = input(f"Select drive (1-{len(drives)}) or press Enter to skip: ").strip()
                            if selection:
                                idx = int(selection) - 1
                                if 0 <= idx < len(drives):
                                    selected_device = drives[idx]['device']
                                    print(f"Selected: {selected_device}")
                        except ValueError:
                            print("Invalid selection.")
                
                # Log initial system data
                if selected_device:
                    all_data = system_info.copy()
                    smart_data = self.collect_nvme_smart(selected_device)
                    error_data = self.collect_nvme_errors(selected_device)
                    pcie_data = self.collect_pcie_info(selected_device)
                    
                    all_data.update({
                        'smart_critical_warning': smart_data['critical_warning'],
                        'smart_temperature_c': smart_data['temperature_c'],
                        'smart_available_spare_pct': smart_data['available_spare_pct'],
                        'smart_percentage_used': smart_data['percentage_used'],
                        'error_count_media': error_data['media_errors'],
                        'error_count_correctable': error_data['correctable_errors'],
                        'pcie_link_speed': pcie_data['link_speed'],
                        'pcie_link_width': pcie_data['link_width']
                    })
                    
                    self.log_to_csv(all_data, "initial_collection")
            
            elif choice == '2':
                # Format drive
                if not selected_device:
                    print("Please select a drive first (option 1).")
                else:
                    self.format_drive_menu(selected_device)
            
            elif choice == '3':
                # Pre-conditioning
                if not selected_device:
                    print("Please select a drive first (option 1).")
                else:
                    self.run_preconditioning_menu(selected_device)
            
            elif choice == '4':
                # Performance testing
                if not selected_device:
                    print("Please select a drive first (option 1).")
                else:
                    results = self.run_fio_tests_menu(selected_device)
                    if results:
                        # Log performance results
                        perf_data = self.collect_system_info()
                        perf_data.update(results)
                        self.log_to_csv(perf_data, "performance_test")
            
            elif choice == '5':
                # Post-test data collection
                if not selected_device:
                    print("Please select a drive first (option 1).")
                else:
                    print("Collecting post-test data...")
                    system_info = self.collect_system_info()
                    smart_data = self.collect_nvme_smart(selected_device)
                    error_data = self.collect_nvme_errors(selected_device)
                    pcie_data = self.collect_pcie_info(selected_device)
                    
                    all_data = system_info.copy()
                    all_data.update({
                        'smart_critical_warning': smart_data['critical_warning'],
                        'smart_temperature_c': smart_data['temperature_c'],
                        'smart_available_spare_pct': smart_data['available_spare_pct'],
                        'smart_percentage_used': smart_data['percentage_used'],
                        'error_count_media': error_data['media_errors'],
                        'error_count_correctable': error_data['correctable_errors'],
                        'pcie_link_speed': pcie_data['link_speed'],
                        'pcie_link_width': pcie_data['link_width']
                    })
                    
                    self.log_to_csv(all_data, "post_test_collection")
                    print("Post-test data collection completed.")
            
            elif choice == '6':
                # Generate report
                if os.path.exists(self.csv_file):
                    print(f"\nTest results saved in: {self.csv_file}")
                    try:
                        df = pd.read_csv(self.csv_file)
                        print(f"Total test records: {len(df)}")
                        print("\nTest phases recorded:")
                        for phase in df['test_phase'].unique():
                            count = len(df[df['test_phase'] == phase])
                            print(f"  {phase}: {count} records")
                    except Exception as e:
                        print(f"Error reading CSV file: {e}")
                else:
                    print("No test results file found. Run some tests first.")
            
            elif choice == '7':
                # Exit
                print("Exiting SSD Test Suite. Goodbye!")
                break
            
            else:
                print("Invalid option. Please select 1-7.")

def main():
    """Main entry point."""
    try:
        tester = SSDTester()
        tester.main_menu()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Exiting...")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
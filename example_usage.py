#!/usr/bin/env python3
"""
Example usage of the SSDTester utility class.
This demonstrates how to use the refactored non-interactive SSD testing suite.
"""

from ssd_test_suite import SSDTester
import json

def main():
    """Demonstrate programmatic usage of SSDTester."""
    
    # Create tester instance with verbose output
    print("=== SSD Tester Utility Example ===")
    tester = SSDTester(verbose=True)
    
    # Step 1: Collect system information
    print("\n1. Collecting system information...")
    system_info = tester.collect_system_info()
    print(f"   CPU: {system_info.get('cpu_model', 'Unknown')}")
    print(f"   Cores: {system_info.get('cpu_cores', 0)}")
    print(f"   Memory: {system_info.get('total_memory_gb', 0)} GB")
    
    # Step 2: Detect NVMe drives
    print("\n2. Detecting NVMe drives...")
    drives = tester.detect_nvme_drives()
    if not drives:
        print("   No NVMe drives found. Exiting.")
        return
    
    print(f"   Found {len(drives)} NVMe drive(s):")
    for i, drive in enumerate(drives):
        size_gb = drive['size'] / (1024**3) if drive['size'] > 0 else 0
        print(f"   [{i}] {drive['device']}: {drive['model']} ({size_gb:.1f} GB)")
    
    # Step 3: Select a device for testing
    device = drives[0]['device']  # Select first drive
    print(f"\n3. Selecting device for testing: {device}")
    tester.select_device(device)
    
    # Step 4: Collect device-specific data
    print("\n4. Collecting device data...")
    tester.collect_all_device_data(device)
    
    # Display SMART data
    smart_data = tester.get_smart_data(device)
    print(f"   Temperature: {smart_data.get('temperature_c', 'Unknown')}°C")
    print(f"   Percentage used: {smart_data.get('percentage_used', 'Unknown')}%")
    
    # Step 5: Example of running tests (commented out for safety)
    print("\n5. Example test operations (commented for safety):")
    print("   # Format drive:")
    print(f"   # tester.format_drive('{device}', 'quick', confirm=True)")
    print("   ")
    print("   # Run pre-conditioning:")
    print(f"   # tester.run_preconditioning('{device}', 'random')")
    print("   ")
    print("   # Run performance tests:")
    print(f"   # tester.run_fio_tests('{device}', ['randread', 'randwrite'])")
    
    # Step 6: Export all collected data
    print("\n6. Exporting collected data...")
    all_data = tester.export_all_data()
    
    # Show summary of collected data
    print("   Data collected:")
    print(f"   - System info: {len(all_data['system_info'])} fields")
    print(f"   - NVMe drives: {len(all_data['nvme_drives'])} drives")
    print(f"   - SMART data: {len(all_data['smart_data'])} devices")
    print(f"   - Test history: {len(all_data['test_history'])} operations")
    
    # Step 7: Save to JSON for analysis
    print("\n7. Saving data to JSON file...")
    with open('ssd_test_data.json', 'w') as f:
        json.dump(all_data, f, indent=2)
    print("   Data saved to: ssd_test_data.json")
    
    # Step 8: Save to CSV
    print("\n8. Saving to CSV...")
    success = tester.save_to_csv('ssd_results.csv')
    if success:
        print("   CSV saved to: ssd_results.csv")
    
    print("\n=== Example completed successfully! ===")
    print("\nTo run actual tests, uncomment the test operations above and run with:")
    print("sudo python3 example_usage.py")

def run_actual_tests_example():
    """Example of running actual destructive tests (use with caution!)"""
    
    print("WARNING: This function runs DESTRUCTIVE tests!")
    print("Uncommenting and running this will DESTROY DATA on the selected drive!")
    
    tester = SSDTester(verbose=True)
    drives = tester.detect_nvme_drives()
    
    if not drives:
        print("No drives found.")
        return
    
    device = drives[0]['device']
    print(f"Selected device: {device}")
    
    # DANGEROUS OPERATIONS - Only run if you're sure!
    # Uncomment these lines ONLY if you want to actually test:
    
    # # Format the drive (DESTROYS ALL DATA!)
    # print("Formatting drive...")
    # tester.format_drive(device, 'quick', confirm=True)
    # 
    # # Run pre-conditioning (takes hours!)
    # print("Running pre-conditioning...")
    # tester.run_preconditioning(device, 'random')
    # 
    # # Run performance tests
    # print("Running performance tests...")
    # tester.run_fio_tests(device, ['randread', 'randwrite', 'seqread', 'seqwrite'])
    # 
    # # Export results
    # all_data = tester.export_all_data()
    # with open('complete_test_results.json', 'w') as f:
    #     json.dump(all_data, f, indent=2)
    # 
    # tester.save_to_csv('complete_test_results.csv')
    # print("Complete test results saved!")

if __name__ == "__main__":
    main()
    
    # To run actual destructive tests, uncomment this line:
    # run_actual_tests_example()
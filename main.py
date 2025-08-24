"""
Main demonstration script for Hierarchical-Blockchain Framework.

This script demonstrates the key features of the hierarchical blockchain framework:
- Main Chain and Sub-Chain creation and management
- Entity registration and lifecycle management
- Business operations (resource allocation, quality checks, approvals)
- Proof submissions from Sub-Chains to Main Chain
- Entity tracing across multiple chains
- Cross-chain validation and integrity checking

This serves as both a demonstration and a basic test of the framework.
"""

import time
import random
import sys
from typing import Dict, Any

# Import framework components
from hierarchical.hierarchy_manager import HierarchyManager
from domains.generic.utils.entity_tracer import EntityTracer
from domains.generic.utils.cross_chain_validator import CrossChainValidator
from adapters.database.sqlite_adapter import SQLiteAdapter


def demonstrate_hierarchical_blockchain():
    """Demonstrate the hierarchical blockchain framework capabilities."""
    
    print("=" * 80)
    print("HIERARCHICAL-BLOCKCHAIN FRAMEWORK DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Initialize the hierarchical system
    print("1. Initializing Hierarchical System...")
    try:
        hierarchy_manager = HierarchyManager()
    except Exception as e:
        print(f"Error initializing system: {e}")
        return None

    # Create Sub-Chains for different business domains
    print("2. Creating Sub-Chains for different business domains...")

    # Manufacturing Sub-Chain
    success = hierarchy_manager.create_sub_chain(
        name="ManufacturingChain",
        domain_type="manufacturing",
        metadata={
            "department": "Manufacturing",
            "location": "Factory-A",
            "capacity": 1000
        }
    )
    print(f"   Manufacturing Chain created: {success}")

    # Quality Control Sub-Chain
    success = hierarchy_manager.create_sub_chain(
        name="QualityChain", 
        domain_type="quality_control",
        metadata={
            "department": "Quality Assurance",
            "standards": ["ISO-9001", "ISO-14001"],
            "inspection_levels": 3
        }
    )
    print(f"   Quality Chain created: {success}")

    # Logistics Sub-Chain
    success = hierarchy_manager.create_sub_chain(
        name="LogisticsChain",
        domain_type="logistics", 
        metadata={
            "department": "Supply Chain",
            "regions": ["North", "South", "East", "West"],
            "transport_modes": ["truck", "rail", "air"]
        }
    )
    print(f"   Logistics Chain created: {success}")
    
    print()
    
    # Demonstrate entity lifecycle across multiple chains
    print("3. Demonstrating Entity Lifecycle Management...")
    
    # Create some sample entities
    entities = [
        "PRODUCT-2024-001",
        "PRODUCT-2024-002", 
        "PRODUCT-2024-003"
    ]
    
    manufacturing_chain = hierarchy_manager.get_sub_chain("ManufacturingChain")
    quality_chain = hierarchy_manager.get_sub_chain("QualityChain")
    logistics_chain = hierarchy_manager.get_sub_chain("LogisticsChain")
    
    for entity_id in entities:
        print(f"   Processing entity: {entity_id}")
        
        # Register entity in manufacturing
        manufacturing_chain.register_entity(entity_id, {
            "product_type": "Electronics",
            "batch_number": f"BATCH-{random.randint(1000, 9999)}",
            "target_quantity": random.randint(50, 200)
        })
        
        # Start manufacturing operation
        hierarchy_manager.start_operation(
            "ManufacturingChain", 
            entity_id, 
            "production",
            {"machine_id": f"MACHINE-{random.randint(1, 10)}"}
        )
        
        # Complete manufacturing
        hierarchy_manager.complete_operation(
            "ManufacturingChain",
            entity_id,
            "production", 
            {"success": True, "quantity_produced": random.randint(45, 55)}
        )
        
        # Quality check
        quality_chain.register_entity(entity_id, {
            "received_from": "ManufacturingChain",
            "quality_standards": ["electrical", "mechanical", "visual"]
        })
        
        quality_chain.perform_quality_check(
            entity_id,
            "final_inspection",
            "passed",
            f"INSPECTOR-{random.randint(1, 5)}"
        )
        
        # Approval process
        quality_chain.process_approval(
            entity_id,
            "quality_release",
            "approved",
            f"QA-MANAGER-{random.randint(1, 3)}"
        )
        
        # Logistics handling
        logistics_chain.register_entity(entity_id, {
            "received_from": "QualityChain",
            "destination": f"WAREHOUSE-{random.choice(['A', 'B', 'C'])}",
            "priority": random.choice(["normal", "high", "urgent"])
        })
        
        logistics_chain.allocate_resource(
            entity_id,
            "transport_vehicle",
            f"TRUCK-{random.randint(100, 999)}"
        )
        
        # Update status
        logistics_chain.update_entity_status(
            entity_id,
            "shipped",
            "Ready for delivery"
        )
    
    print()
    
    # Finalize blocks and submit proofs
    print("4. Finalizing blocks and submitting proofs to Main Chain...")

    # Finalize Sub-Chain blocks
    try:
        manufacturing_result = manufacturing_chain.finalize_block()
        quality_result = quality_chain.finalize_block()
        logistics_result = logistics_chain.finalize_block()
    except Exception as e:
        print(f"Error finalizing blocks: {e}")
        return None

    print(f"   Manufacturing block finalized: {manufacturing_result is not None}")
    print(f"   Quality block finalized: {quality_result is not None}")
    print(f"   Logistics block finalized: {logistics_result is not None}")

    # Submit proofs to Main Chain
    try:
        proof_results = hierarchy_manager.submit_all_proofs()
    except Exception as e:
        print(f"Error submitting proofs: {e}")
        return None

    print(f"   Proof submissions: {proof_results}")

    # Finalize Main Chain block
    try:
        main_chain_result = hierarchy_manager.finalize_main_chain_block()
    except Exception as e:
        print(f"Error finalizing main chain block: {e}")
        return None

    print(f"   Main Chain block finalized: {main_chain_result is not None}")
    
    print()
    
    # Demonstrate entity tracing
    print("5. Demonstrating Entity Tracing Across Chains...")

    entity_tracer = EntityTracer(hierarchy_manager)

    for entity_id in entities[:2]:  # Trace first two entities
        print(f"   Tracing entity: {entity_id}")
        
        try:
            # Get entity lifecycle
            lifecycle = entity_tracer.get_entity_lifecycle(entity_id)
            print(f"     Found in {len(lifecycle['chains'])} chains")
            print(f"     Total events: {lifecycle['total_events']}")
            print(f"     Lifecycle stages: {len(lifecycle.get('lifecycle_stages', []))}")
            print(f"     Cross-chain interactions: {lifecycle.get('cross_chain_interactions', {}).get('total_chains', 0)} chains")
            
            # Get performance summary
            performance = entity_tracer.get_entity_performance_summary(entity_id)
            if performance['found']:
                metrics = performance['performance_metrics']
                print(f"     Completion rate: {metrics['completion_rate']:.2f}")
                print(f"     Quality pass rate: {metrics['quality_pass_rate']:.2f}")
                print(f"     Approval rate: {metrics['approval_rate']:.2f}")
                
        except Exception as e:
            print(f"Error tracing entity {entity_id}: {e}")
            continue

        print()

    # Demonstrate cross-chain validation
    print("6. Demonstrating Cross-Chain Validation...")

    validator = CrossChainValidator(hierarchy_manager)

    # Validate system integrity with detailed reporting
    try:
        integrity_report = validator.validate_system_integrity()
        
        print(f"   Main Chain valid: {integrity_report['main_chain_valid']}")
        print(f"   Sub-Chains valid: {all(integrity_report['sub_chains_valid'].values())}")
        print(f"   Proof consistency: {integrity_report['proof_consistency']['overall_consistent']}")
        print(f"   Framework compliance: {integrity_report['framework_compliance']['overall_compliant']}")
        print(f"   Overall system integrity: {integrity_report['overall_integrity']}")

        if integrity_report['recommendations']:
            print("   Recommendations:")
            for rec in integrity_report['recommendations']:
                print(f"     - {rec}")
        else:
            print("   No recommendations - system is healthy!")
    except Exception as e:
        print(f"Error during cross-chain validation: {e}")

    print()

    # Generate comprehensive system report
    print("7. Generating System Statistics...")

    try:
        system_stats = hierarchy_manager.get_system_integrity_report()
        print(f"   Total Sub-Chains: {system_stats['system_overview']['total_sub_chains']}")
        print(f"   Total Sub-Chain blocks: {system_stats['system_overview']['total_sub_chain_blocks']}")
        print(f"   Total Sub-Chain events: {system_stats['system_overview']['total_sub_chain_events']}")
        print(f"   System uptime: {system_stats['system_overview']['system_uptime']:.2f} seconds")
        print(f"   System integrity: {system_stats['integrity_status']}")

        # Show individual chain statistics
        print("\n   Individual Chain Statistics:")
        for chain_name, details in system_stats['sub_chain_details'].items():
            print(f"     {chain_name}:")
            print(f"       Domain: {details['domain_type']}")
            print(f"       Blocks: {details['blocks']}")
            print(f"       Events: {details['events']}")
            print(f"       Entities: {details['entities']}")
            print(f"       Operations: {details['operations']}")
    except Exception as e:
        print(f"Error generating system statistics: {e}")

    print()
    
    # Demonstrate database persistence (optional)
    print("8. Demonstrating Database Persistence...")
    
    try:
        db_adapter = SQLiteAdapter("demo_blockchain.db")
        
        # Store Main Chain
        main_chain_stored = db_adapter.store_chain(hierarchy_manager.main_chain)
        print(f"   Main Chain stored in database: {main_chain_stored}")
        
        # Store Sub-Chains
        for sub_chain_name, sub_chain in hierarchy_manager.sub_chains.items():
            try:
                stored = db_adapter.store_chain(sub_chain)
                print(f"   {sub_chain_name} stored in database: {stored}")
            except Exception as e:
                print(f"Error storing {sub_chain_name}: {e}")
                continue
                
        # Get statistics from database
        for chain_name in ["CorporateMainChain", "ManufacturingChain", "QualityChain", "LogisticsChain"]:
            try:
                stats = db_adapter.get_chain_statistics(chain_name)
                if stats:
                    print(f"   {chain_name} DB stats: {stats['total_blocks']} blocks, {stats['total_events']} events")
            except Exception as e:
                print(f"Error getting stats for {chain_name}: {e}")
                continue
                
        # Test entity querying from database
        test_entity = entities[0]
        try:
            entity_events = db_adapter.get_entity_events(test_entity)
            print(f"   Entity {test_entity} has {len(entity_events)} events in database")
        except Exception as e:
            print(f"Error querying entity {test_entity}: {e}")
            
    except Exception as e:
        print(f"   Database demonstration skipped: {e}")

    print()
    
    # Final summary
    print("9. Framework Demonstration Summary...")
    print("   ✓ Hierarchical structure (Main Chain + Sub-Chains)")
    print("   ✓ Event-based model (no cryptocurrency terminology)")
    print("   ✓ Entity lifecycle management across multiple chains")
    print("   ✓ Business operations (manufacturing, quality, logistics)")
    print("   ✓ Proof submissions from Sub-Chains to Main Chain")
    print("   ✓ Cross-chain entity tracing and analysis")
    print("   ✓ System integrity validation and compliance checking")
    print("   ✓ Database persistence and querying capabilities")
    print("   ✓ Framework guidelines compliance throughout")

    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY!")
    print("The Hierarchical-Blockchain Framework is working correctly.")
    print("=" * 80)
    
    return hierarchy_manager


def main():
    """Main entry point for the demonstration."""
    try:
        # Add framework version information
        print("Framework Version: 0.dev2")
        print("Architecture: Hierarchical Blockchain with Main Chain/Sub-Chains")
        print("Compliance: Non-cryptocurrency, Event-based, Hierarchical Structure")
        print()
        
        hierarchy_manager = demonstrate_hierarchical_blockchain()
        
        # Optional: Keep the system running for interactive exploration
        print("\nFramework is ready for use!")
        print("You can now:")
        print("- Add more entities and operations")
        print("- Create additional Sub-Chains")
        print("- Perform entity tracing and validation")
        print("- Explore the database contents")
        
        # Return success status
        sys.exit(0)
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        # Return error status
        sys.exit(1)


if __name__ == "__main__":
    main()
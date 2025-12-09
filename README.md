# HieraChain Framework

![Python Versions](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE-APACHE)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE-MIT)

## Overview

HieraChain is an advanced enterprise blockchain framework designed specifically for business applications without any cryptocurrency concepts. Unlike traditional blockchain platforms focused on digital currencies, HieraChain focuses on providing a secure, hierarchical structure for managing business operations and processes.

The framework implements a multi-layer architecture where Main Chains supervise Sub-Chains, enabling scalable and secure business process management. All operations within the framework are referred to as "events" rather than "transactions," emphasizing its focus on business applications.

## Core Architecture

### Hierarchical Structure

The framework follows a hierarchical architecture consisting of:

1. **Main Chain (Supervisor)**
   - Acts as the root authority in the system
   - Stores only cryptographic proofs from Sub-Chains, not detailed domain data
   - Maintains the integrity of the entire hierarchical system
   - Provides proof verification and chain coordination

2. **Sub-Chains (Domain Experts)**
   - Handle domain-specific business operations
   - Store detailed domain events and data
   - Submit cryptographic proofs to the Main Chain
   - Operate independently but are supervised by the Main Chain

```
Main Chain (Supervisor)
├── Sub-Chain 1 (Domain A)
├── Sub-Chain 2 (Domain B)
└── Sub-Chain 3 (Domain C)
```

### Key Design Principles

- **Event-Based Model**: Business operations are represented as "events" rather than cryptocurrency transactions
- **Proof Submission**: Sub-Chains submit cryptographic proofs to the Main Chain for verification
- **Data Segregation**: Detailed domain data stays in Sub-Chains; only proofs reach the Main Chain
- **Entity Identification**: Entities are identified through metadata fields, not as identifiers
- **Scalability**: The hierarchical structure enables horizontal scaling across multiple domains

## Core Components

### Blockchain Core

The foundation of HieraChain includes:
- **[Blockchain](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/core/blockchain.py)**: Base blockchain class implementing fundamental operations
- **[Block](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/core/block.py)**: Data structure representing individual blocks containing multiple events
- **Consensus Mechanisms**: Implementation of Proof of Authority (PoA) consensus algorithm suitable for enterprise environments

### Hierarchical Management

The hierarchical structure is managed through:
- **[MainChain](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/hierarchical/main_chain.py)**: Root authority implementation that stores proofs from Sub-Chains
- **[SubChain](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/hierarchical/sub_chain.py)**: Domain-specific chain implementation handling detailed business operations
- **[HierarchyManager](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/hierarchical/hierarchy_manager.py)**: Component coordinating interactions between Main Chain and Sub-Chains

### Domain Layer

HieraChain provides a flexible domain layer for modeling business operations:
- **Generic Domain Implementation**: Ready-to-use domain chain for common business scenarios
- **Event System**: Structured event creation and management ([EventFactory](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/domains/generic/events/domain_event.py))
- **Business Rules Engine**: Framework for defining and validating domain-specific business rules

### Security Features

Comprehensive security mechanisms include:
- **[Key Management](https://github.com/VanDung-dev/HieraChain/blob/main/hierachain/security/key_manager.py)**: API key generation, validation, and revocation
- **Identity Management**: User and application identity handling
- **Access Control**: Permission-based resource access control
- **Certificate Management**: Digital certificate handling for secure communications

### API Layer

RESTful API interfaces for external integration:
- **V1 API**: Core endpoints for chain management, event handling, and proof submission
- **V2 API**: Enhanced endpoints with improved features and performance
- **V3 API**: Latest API version with advanced verification capabilities

## Key Features

### Multi-Organization Support
Secure collaboration between different organizations with isolated data storage and controlled access policies.

### Privacy Controls
Private data collections with fine-grained access policies, ensuring sensitive information remains protected.

### Enterprise Security
Advanced identity management, certificate-based authentication, and robust access control mechanisms.

### Scalable Architecture
Horizontal scaling through multiple Sub-Chains handling different business domains while maintaining centralized oversight through the Main Chain.

### Event-Based Operations
All business activities are modeled as events, allowing for comprehensive audit trails and historical tracking.

### Proof Verification
Cryptographic proof submission and verification mechanism ensuring data integrity across the hierarchy.

### Cross-Chain Tracing
Entity tracing capabilities across multiple chains for comprehensive business process visibility.

### Domain-Specific Operations
Support for various business operations including:
- Resource allocation
- Quality checks
- Approval workflows
- Compliance monitoring
- Status updates
- Operation tracking

## Use Cases

HieraChain is ideal for enterprise applications requiring:
- Supply chain management
- Regulatory compliance tracking
- Audit trail maintenance
- Multi-department workflow coordination
- Secure inter-organization data sharing
- Quality assurance processes
- Asset tracking and management

## Technical Capabilities

### Data Management
- Efficient event storage and retrieval
- Entity-based querying across chains
- Statistical analysis and reporting
- Performance monitoring

### Integration Support
- RESTful API interfaces
- ERP system adapters
- Database connectivity
- Storage flexibility (file-based, Redis, SQLite)

### Monitoring and Maintenance
- Performance monitoring tools
- Alert systems for anomalies
- Recovery mechanisms for error handling
- Risk analysis and mitigation strategies

### Development Features
- Modular architecture for easy extension
- Comprehensive testing suite
- Configuration management
- CLI tools for administration

## Benefits

1. **Business-Focused**: Designed specifically for enterprise applications without cryptocurrency distractions
2. **Scalable**: Hierarchical structure allows for horizontal scaling across business domains
3. **Secure**: Robust security mechanisms including identity management and access controls
4. **Flexible**: Domain-agnostic design allows customization for various business needs
5. **Auditable**: Complete event tracking and proof verification ensure regulatory compliance
6. **Maintainable**: Clean separation of concerns between Main Chain supervision and Sub-Chain operations

HieraChain represents a new approach to blockchain technology in enterprise environments, focusing on business process management rather than financial transactions, providing a solid foundation for building secure, scalable, and compliant business applications.

## License

This project is dual licensed under either the [Apache-2.0 License](LICENSE-APACHE) or the [MIT License](LICENSE-MIT). You may choose either license.

---

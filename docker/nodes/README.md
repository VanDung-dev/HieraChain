# Docker Nodes Directory

## ⚠️ IMPORTANT WARNING ⚠️

**These cryptographic keys are for STRESS TESTING purposes ONLY.**

The node identities and cryptographic materials contained in this directory (`docker/nodes/`) are generated exclusively for:

- **Stress testing** of the HieraChain consensus mechanisms
- **Load testing** of the distributed verification system  
- **Development and integration testing** in isolated environments
- **Docker/Kubernetes deployment simulations**

## 🚫 PRODUCTION USE STRICTLY PROHIBITED

**NEVER use these keys in any production environment.** These keys:

- Are publicly exposed in this repository
- Have no real-world security value
- Are not protected by proper key management systems
- Are shared across all test deployments
- Have no revocation or rotation mechanisms

## 🔐 Production Deployment Requirements

For production deployments, you MUST:

1. **Generate new cryptographic keys** using the HieraChain key management system
2. **Store keys securely** using enterprise key management (HSM, KMS, or secure vault)
3. **Implement proper key rotation** policies
4. **Use unique keys per node** with proper access controls
5. **Never commit keys** to version control
6. **Enable audit logging** for all key operations

## 📁 Directory Structure

```
docker/nodes/
├── README.md              # This file
├── peers.json             # Peer registry for testing
├── node1/                 # Test node 1 identity
│   └── identity.json      # Node 1 cryptographic materials
├── node2/                 # Test node 2 identity
│   └── identity.json      # Node 2 cryptographic materials
├── node3/                 # Test node 3 identity
│   └── identity.json      # Node 3 cryptographic materials
└── node4/                 # Test node 4 identity
    └── identity.json      # Node 4 cryptographic materials
```

## 🔧 Key Contents

Each `identity.json` file contains:

- `node_id`: Unique identifier for the test node
- `msp_id`: Membership Service Provider identifier
- `signing_key`: Private key for event signing (ED25519)
- `signing_public_key`: Corresponding public key
- `transport_secret_key`: Private key for secure transport (Curve25519)
- `transport_public_key`: Corresponding public key

## 🛡️ Security Best Practices

When running stress tests:

1. **Isolate test networks** from production systems
2. **Use separate Docker networks** for test deployments
3. **Clean up containers** after testing completes
4. **Rotate test keys** periodically if reusing
5. **Monitor resource usage** during stress tests
6. **Review audit logs** for any anomalies

## 📖 Additional Resources

- [Security Documentation](https://docs.hierachain.org/security/encryption-keys/)
- [Deployment Guide](https://docs.hierachain.org/architecture/deployment/)
- [Key Management](https://docs.hierachain.org/security/authorization-access-control/)

---

**Remember**: These keys exist solely to facilitate testing. Treat them with the same disregard you would give to any publicly shared test credentials. **Production systems require properly managed, unique cryptographic materials generated through secure processes.**
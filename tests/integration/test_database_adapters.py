"""
Integration tests for database adapters with core blockchain components
"""

import unittest

from hierarchical_blockchain.core.blockchain import Blockchain
from hierarchical_blockchain.core.block import Block


class TestDatabaseAdaptersIntegration(unittest.TestCase):
    """Test the integration between database adapters and core blockchain components"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_chain = Blockchain("test_chain")
        
        # Add some test events
        self.test_events = [
            {
                "entity_id": "entity_1",
                "event": "create_order",
                "timestamp": 1000000000,
                "details": {
                    "order_id": "order_123",
                    "amount": 100.0
                }
            },
            {
                "entity_id": "entity_2",
                "event": "update_inventory",
                "timestamp": 1000000001,
                "details": {
                    "product_id": "product_456",
                    "quantity": 5
                }
            }
        ]
        
        # Add events to blockchain
        for event in self.test_events:
            self.test_chain.add_event(event)
        
        # Finalize a block
        self.test_block = self.test_chain.finalize_block()

    def test_blockchain_to_dict_conversion(self):
        """Test that blockchain can be converted to dictionary format for storage"""
        chain_dict = self.test_chain.to_dict()
        
        self.assertIsInstance(chain_dict, dict)
        self.assertEqual(chain_dict["name"], "test_chain")
        self.assertEqual(len(chain_dict["chain"]), 2)  # Genesis block + our block
        self.assertEqual(len(chain_dict["pending_events"]), 0)  # We finalized our events
        
        # Check block structure
        block_dict = chain_dict["chain"][1]  # Skip genesis block
        self.assertEqual(block_dict["index"], 1)
        self.assertEqual(len(block_dict["events"]), 2)
        self.assertEqual(block_dict["events"][0]["entity_id"], "entity_1")

    def test_blockchain_from_dict_reconstruction(self):
        """Test that blockchain can be reconstructed from dictionary data"""
        chain_dict = self.test_chain.to_dict()
        reconstructed_chain = Blockchain.from_dict(chain_dict)
        
        self.assertEqual(reconstructed_chain.name, self.test_chain.name)
        self.assertEqual(len(reconstructed_chain.chain), len(self.test_chain.chain))
        self.assertEqual(len(reconstructed_chain.pending_events), len(self.test_chain.pending_events))
        
        # Check that blocks match
        original_block = self.test_chain.chain[1]  # Skip genesis
        reconstructed_block = reconstructed_chain.chain[1]  # Skip genesis
        
        self.assertEqual(reconstructed_block.index, original_block.index)
        self.assertEqual(reconstructed_block.hash, original_block.hash)
        self.assertEqual(reconstructed_block.previous_hash, original_block.previous_hash)
        self.assertEqual(len(reconstructed_block.events), len(original_block.events))

    def test_block_to_dict_conversion(self):
        """Test that individual blocks can be converted to dictionary format"""
        block = self.test_chain.chain[1]  # Skip genesis block
        block_dict = block.to_dict()
        
        self.assertIsInstance(block_dict, dict)
        self.assertEqual(block_dict["index"], 1)
        self.assertEqual(block_dict["hash"], block.hash)
        self.assertEqual(block_dict["previous_hash"], block.previous_hash)
        self.assertEqual(len(block_dict["events"]), 2)

    def test_block_from_dict_reconstruction(self):
        """Test that blocks can be reconstructed from dictionary data"""
        block = self.test_chain.chain[1]  # Skip genesis block
        block_dict = block.to_dict()
        reconstructed_block = Block.from_dict(block_dict)
        
        self.assertEqual(reconstructed_block.index, block.index)
        self.assertEqual(reconstructed_block.hash, block.hash)
        self.assertEqual(reconstructed_block.previous_hash, block.previous_hash)
        self.assertEqual(len(reconstructed_block.events), len(block.events))
        
        # Check events match
        for orig_event, recon_event in zip(block.events, reconstructed_block.events):
            self.assertEqual(recon_event["entity_id"], orig_event["entity_id"])
            self.assertEqual(recon_event["event"], orig_event["event"])

if __name__ == '__main__':
    unittest.main()
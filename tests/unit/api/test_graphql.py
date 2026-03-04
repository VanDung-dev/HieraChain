"""
Test suite for the HieraChain GraphQL API.
"""

from unittest.mock import patch, MagicMock


def test_graphql_schema_import():
    """Test that GraphQL schema can be imported"""
    from hierachain.api.graphql.schema import schema
    assert schema is not None


def test_graphql_query_all_chains():
    """Test GraphQL query for all chains"""
    from hierachain.api.graphql.schema import schema
    
    # Mock the hierarchy manager
    mock_main_chain = MagicMock()
    mock_main_chain.get_latest_block.return_value = MagicMock(index=0, hash="abc123")
    mock_main_chain.chain = []
    
    mock_sub_chain = MagicMock()
    mock_sub_chain.get_latest_block.return_value = None
    mock_sub_chain.chain = []
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = mock_main_chain
    mock_manager.get_all_sub_chains.return_value = {"TestChain": mock_sub_chain}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        # Execute query
        query = """
        {
            allChains {
                chainName
                blockCount
                status
            }
        }
        """
        result = schema.execute(query)
        
        assert result.errors is None
        assert result.data is not None
        assert 'allChains' in result.data


def test_graphql_query_chain_status():
    """Test GraphQL query for specific chain status"""
    from hierachain.api.graphql.schema import schema
    
    # Mock the chain
    mock_chain = MagicMock()
    mock_block = MagicMock()
    mock_block.index = 5
    mock_block.hash = "block_hash_123"
    mock_chain.get_latest_block.return_value = mock_block
    mock_chain.chain = [1, 2, 3, 4, 5]
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = None
    mock_manager.get_all_sub_chains.return_value = {"TestChain": mock_chain}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        query = """
        {
            chainStatus(chainName: "TestChain") {
                chainName
                blockCount
                latestBlockIndex
                latestBlockHash
                status
            }
        }
        """
        result = schema.execute(query)
        
        assert result.errors is None
        assert result.data is not None
        data = result.data['chainStatus']
        assert data['chainName'] == "TestChain"
        assert data['blockCount'] == 5
        assert data['latestBlockIndex'] == 5
        assert data['status'] == "active"


def test_graphql_query_block():
    """Test GraphQL query for a specific block"""
    from hierachain.api.graphql.schema import schema
    
    # Mock the block
    mock_block = MagicMock()
    mock_block.index = 1
    mock_block.hash = "abc123"
    mock_block.previous_hash = "prev456"
    mock_block.timestamp = 1234567890.0
    mock_block.nonce = "nonce123"
    mock_block.events = []
    mock_block.metadata = MagicMock()
    mock_block.metadata.validator_signatures = ["sig1", "sig2"]
    
    # Mock the chain - use chain attribute instead of get_block method
    mock_chain = MagicMock()
    mock_chain.chain = [None, mock_block]  # Index 0 is None (genesis), index 1 is our block
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = None
    mock_manager.get_all_sub_chains.return_value = {"TestChain": mock_chain}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        query = """
        {
            block(chainName: "TestChain", blockIndex: 1) {
                index
                hash
                previousHash
                timestamp
                nonce
            }
        }
        """
        result = schema.execute(query)
        
        assert result.errors is None
        assert result.data is not None
        data = result.data['block']
        assert data['index'] == 1
        assert data['hash'] == "abc123"
        assert data['previousHash'] == "prev456"


def test_graphql_query_blocks():
    """Test GraphQL query for multiple blocks"""
    from hierachain.api.graphql.schema import schema
    
    # Mock blocks
    mock_block1 = MagicMock()
    mock_block1.index = 0
    mock_block1.hash = "hash0"
    mock_block1.previous_hash = ""
    mock_block1.timestamp = 1000.0
    mock_block1.nonce = "n0"
    mock_block1.events = []
    mock_block1.metadata = None
    
    mock_block2 = MagicMock()
    mock_block2.index = 1
    mock_block2.hash = "hash1"
    mock_block2.previous_hash = "hash0"
    mock_block2.timestamp = 2000.0
    mock_block2.nonce = "n1"
    mock_block2.events = []
    mock_block2.metadata = None
    
    # Mock the chain - use chain attribute instead of get_blocks_range method
    mock_chain = MagicMock()
    mock_chain.chain = [mock_block1, mock_block2]
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = None
    mock_manager.get_all_sub_chains.return_value = {"TestChain": mock_chain}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        query = """
        {
            blocks(chainName: "TestChain", limit: 10) {
                index
                hash
            }
        }
        """
        result = schema.execute(query)
        
        assert result.errors is None
        assert result.data is not None
        blocks = result.data['blocks']
        assert len(blocks) == 2
        assert blocks[0]['index'] == 0
        assert blocks[1]['index'] == 1


def test_graphql_query_events():
    """Test GraphQL query for events"""
    from hierachain.api.graphql.schema import schema
    
    # Mock events
    mock_event1 = MagicMock()
    mock_event1.entity_id = "entity1"
    mock_event1.event_type = "created"  # Use event_type to match GraphQL schema
    mock_event1.event = "created"  # Also set event for Blockchain compatibility
    mock_event1.data = {"key": "value"}
    mock_event1.timestamp = 1234567890.0
    mock_event1.signature = "sig1"
    
    mock_event2 = MagicMock()
    mock_event2.entity_id = "entity2"
    mock_event2.event_type = "updated"
    mock_event2.event = "updated"
    mock_event2.data = {"key2": "value2"}
    mock_event2.timestamp = 1234567900.0
    mock_event2.signature = "sig2"
    
    # Mock the block containing events
    mock_block = MagicMock()
    mock_block.events = [mock_event1, mock_event2]
    
    # Mock the chain - use chain attribute with blocks containing events
    mock_chain = MagicMock()
    mock_chain.chain = [mock_block]
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = None
    mock_manager.get_all_sub_chains.return_value = {"TestChain": mock_chain}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        query = """
        {
            events(chainName: "TestChain", limit: 10) {
                entityId
                eventType
                timestamp
            }
        }
        """
        result = schema.execute(query)
        
        assert result.errors is None
        assert result.data is not None
        events = result.data['events']
        assert len(events) == 2
        assert events[0]['entityId'] == "entity1"
        assert events[0]['eventType'] == "created"


def test_graphql_mutation_add_event():
    """Test GraphQL mutation to add an event"""
    from hierachain.api.graphql.schema import schema
    
    # Mock the chain
    mock_chain = MagicMock()
    mock_chain.add_event.return_value = 5  # Returns block index
    
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = mock_chain
    mock_manager.get_all_sub_chains.return_value = {}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        mutation = """
        mutation {
            addEvent(event: {
                chainName: "main_chain"
                entityId: "entity123"
                eventType: "created"
                details: "{\\"key\\": \\"value\\"}"
            }) {
                success
                blockIndex
                error
            }
        }
        """
        result = schema.execute(mutation)
        
        # Debug: print errors if any
        if result.errors:
            print("Errors:", result.errors)
        if result.data:
            print("Data:", result.data)
        
        assert result.errors is None
        assert result.data is not None


def test_graphql_mutation_add_event_invalid_chain():
    """Test GraphQL mutation with invalid chain name"""
    from hierachain.api.graphql.schema import schema
    
    # Mock the manager with no chains
    mock_manager = MagicMock()
    mock_manager.get_main_chain.return_value = None
    mock_manager.get_all_sub_chains.return_value = {}
    
    with patch('hierachain.api.graphql.schema.get_hierarchy_manager', return_value=mock_manager):
        mutation = """
        mutation {
            addEvent(event: {
                chainName: "NonExistentChain"
                entityId: "entity123"
                eventType: "created"
            }) {
                success
                error
            }
        }
        """
        result = schema.execute(mutation)
        
        assert result.errors is None
        assert result.data is not None
        data = result.data['addEvent']
        assert data['success'] is False
        assert 'not found' in data['error']


def test_graphql_types_exist():
    """Test that all GraphQL types are properly defined"""
    from hierachain.api.graphql.schema import (
        EventType,
        BlockType,
        BlockMetadataType,
        ChainStatusType,
        Query,
        Mutations,
        schema
    )
    
    assert EventType is not None
    assert BlockType is not None
    assert BlockMetadataType is not None
    assert ChainStatusType is not None
    assert Query is not None
    assert Mutations is not None
    assert schema is not None

// Integration test for vector engine and LanceDB
use coderabbit_vector_engine::{VectorEngine, SearchResult};
use coderabbit_shared::Result;
use std::collections::HashMap;

#[tokio::test]
async fn test_vector_engine_integration() -> Result<()> {
    // Initialize vector engine
    let engine = VectorEngine::new().await?;
    
    // Test embedding generation
    let test_texts = vec![
        "fn main() { println!(\"Hello, World!\"); }".to_string(),
        "class HelloWorld { public static void main(String[] args) { System.out.println(\"Hello, World!\"); } }".to_string(),
        "function main() { console.log('Hello, World!'); }".to_string(),
    ];
    
    let embeddings = engine.generate_embeddings(test_texts.clone()).await?;
    assert_eq!(embeddings.len(), 3);
    assert_eq!(embeddings[0].len(), 1536);
    
    // Test batch insertion
    let items = vec![
        ("rust_file_1".to_string(), embeddings[0].clone(), HashMap::from([("language".to_string(), "rust".to_string()), ("file_path".to_string(), "main.rs".to_string())])),
        ("java_file_1".to_string(), embeddings[1].clone(), HashMap::from([("language".to_string(), "java".to_string()), ("file_path".to_string(), "Main.java".to_string())])),
        ("js_file_1".to_string(), embeddings[2].clone(), HashMap::from([("language".to_string(), "javascript".to_string()), ("file_path".to_string(), "main.js".to_string())])),
    ];
    
    engine.batch_insert(items, test_texts.clone()).await?;
    
    // Test similarity search
    let query_embedding = &embeddings[0];
    let search_results = engine.similarity_search(query_embedding, 3).await?;
    
    assert!(!search_results.is_empty());
    assert!(search_results[0].similarity_score > 0.0);
    
    // Test language-specific search
    let code_context_results = engine.search_code_context("fn hello()", "rust", 3).await?;
    assert!(code_context_results.len() <= 3);
    
    // Test statistics
    let stats = engine.get_stats().await?;
    assert!(stats.total_vectors > 0);
    assert_eq!(stats.dimensions, 1536);
    
    println!("Vector engine integration test passed! Total vectors: {}", stats.total_vectors);
    Ok(())
}

#[tokio::test]
async fn test_embedding_consistency() -> Result<()> {
    let engine = VectorEngine::new().await?;
    
    let text1 = "fn test() -> i32 { 42 }";
    let text2 = "fn test() -> i32 { 42 }"; // Same text
    let text3 = "fn other() -> i32 { 24 }"; // Different text
    
    let embedding1 = engine.generate_simple_embedding(text1)?;
    let embedding2 = engine.generate_simple_embedding(text2)?;
    let embedding3 = engine.generate_simple_embedding(text3)?;
    
    let similarity_same = engine.cosine_similarity(&embedding1, &embedding2);
    let similarity_diff = engine.cosine_similarity(&embedding1, &embedding3);
    
    // Same text should have high similarity (should be 1.0)
    assert!((similarity_same - 1.0).abs() < 1e-6);
    
    // Different text should have lower similarity
    assert!(similarity_same > similarity_diff);
    
    println!("Embedding consistency test passed! Same: {}, Different: {}", similarity_same, similarity_diff);
    Ok(())
}

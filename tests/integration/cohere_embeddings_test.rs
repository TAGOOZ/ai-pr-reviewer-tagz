/// Integration test for Cohere embeddings API
use coderabbit_vector_engine::embeddings::CohereEmbeddings;

#[tokio::test]
#[ignore] // Only run with: cargo test --test cohere_embeddings_test -- --ignored
async fn test_cohere_generate_embeddings() {
    // Get Cohere API key from environment
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    let cohere = CohereEmbeddings::new(api_key);

    let texts = vec![
        "The quick brown fox jumps over the lazy dog".to_string(),
        "Machine learning is a subset of artificial intelligence".to_string(),
        "Rust is a systems programming language".to_string(),
    ];

    println!(
        "🧠 Generating embeddings for {} texts using Cohere",
        texts.len()
    );

    match cohere.generate_embeddings(texts.clone()).await {
        Ok(embeddings) => {
            println!("✅ Successfully generated {} embeddings", embeddings.len());
            assert_eq!(embeddings.len(), 3);

            // Cohere embed-english-v3.0 produces 1024-dimensional vectors
            println!("📊 Embedding dimensions: {}", embeddings[0].len());
            assert!(embeddings[0].len() > 0);

            // Verify all embeddings have same dimension
            for (i, emb) in embeddings.iter().enumerate() {
                println!("  Text {}: {} dimensions", i + 1, emb.len());
                assert_eq!(emb.len(), embeddings[0].len());
            }
        }
        Err(e) => {
            println!("❌ Failed to generate embeddings: {}", e);
            panic!("Cohere embedding generation failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_cohere_code_embeddings() {
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    let cohere = CohereEmbeddings::new(api_key);

    let code_snippets = vec![
        r#"
fn main() {
    println!("Hello, world!");
}
"#
        .to_string(),
        r#"
function factorial(n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}
"#
        .to_string(),
    ];

    println!(
        "🧠 Generating code embeddings for {} snippets",
        code_snippets.len()
    );

    match cohere.generate_code_embeddings(code_snippets.clone()).await {
        Ok(embeddings) => {
            println!(
                "✅ Successfully generated {} code embeddings",
                embeddings.len()
            );
            assert_eq!(embeddings.len(), 2);

            for (i, emb) in embeddings.iter().enumerate() {
                println!("  Code snippet {}: {} dimensions", i + 1, emb.len());
                assert!(emb.len() > 0);
            }
        }
        Err(e) => {
            println!("❌ Failed to generate code embeddings: {}", e);
            panic!("Code embedding generation failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_cohere_query_embeddings() {
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    let cohere = CohereEmbeddings::new(api_key);

    let queries = vec![
        "What is machine learning?".to_string(),
        "How does neural network work?".to_string(),
    ];

    println!(
        "🧠 Generating query embeddings for {} queries",
        queries.len()
    );

    match cohere.generate_query_embeddings(queries.clone()).await {
        Ok(embeddings) => {
            println!(
                "✅ Successfully generated {} query embeddings",
                embeddings.len()
            );
            assert_eq!(embeddings.len(), 2);

            for (i, emb) in embeddings.iter().enumerate() {
                println!("  Query {}: {} dimensions", i + 1, emb.len());
                assert!(emb.len() > 0);
            }
        }
        Err(e) => {
            println!("❌ Failed to generate query embeddings: {}", e);
            panic!("Query embedding generation failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_cohere_cosine_similarity() {
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    let cohere = CohereEmbeddings::new(api_key);

    let texts = vec![
        "The cat sits on the mat".to_string(),
        "A feline rests on the rug".to_string(), // Similar meaning
        "The stock market crashed today".to_string(), // Different meaning
    ];

    println!("🧠 Testing semantic similarity with Cohere embeddings");

    match cohere.generate_embeddings(texts.clone()).await {
        Ok(embeddings) => {
            let sim_similar = cohere.cosine_similarity(&embeddings[0], &embeddings[1]);
            let sim_different = cohere.cosine_similarity(&embeddings[0], &embeddings[2]);

            println!("✅ Similarity (similar meanings): {:.4}", sim_similar);
            println!("✅ Similarity (different meanings): {:.4}", sim_different);

            // Embeddings of similar texts should have higher similarity
            assert!(sim_similar > sim_different,
                "Expected similar texts ({:.4}) to have higher similarity than different texts ({:.4})",
                sim_similar, sim_different);

            println!("✅ Semantic similarity test passed!");
        }
        Err(e) => {
            println!("❌ Failed similarity test: {}", e);
            panic!("Similarity test failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_cohere_chunked_embeddings() {
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    let cohere = CohereEmbeddings::new(api_key);

    // Create 10 texts to test chunking
    let texts: Vec<String> = (0..10)
        .map(|i| format!("This is test text number {}", i))
        .collect();

    println!(
        "🧠 Generating chunked embeddings for {} texts (chunk size: 3)",
        texts.len()
    );

    match cohere.generate_embeddings_chunked(texts.clone(), 3).await {
        Ok(embeddings) => {
            println!(
                "✅ Successfully generated {} embeddings in chunks",
                embeddings.len()
            );
            assert_eq!(embeddings.len(), 10);

            // Verify all embeddings have dimensions
            for emb in embeddings.iter() {
                assert!(emb.len() > 0);
            }

            println!("✅ Chunked embedding test passed!");
        }
        Err(e) => {
            println!("❌ Failed chunked embedding test: {}", e);
            panic!("Chunked embedding test failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_cohere_different_models() {
    let api_key =
        std::env::var("COHERE_API_KEY").expect("COHERE_API_KEY environment variable not set");

    // Test with multilingual model
    let cohere = CohereEmbeddings::new(api_key).with_model("embed-multilingual-v3.0".to_string());

    let texts = vec![
        "Hello, how are you?".to_string(),
        "Hola, ¿cómo estás?".to_string(),
        "Bonjour, comment allez-vous?".to_string(),
    ];

    println!("🧠 Testing multilingual model with {} texts", texts.len());

    match cohere.generate_embeddings(texts.clone()).await {
        Ok(embeddings) => {
            println!("✅ Successfully generated embeddings with multilingual model");
            assert_eq!(embeddings.len(), 3);

            for (i, text) in texts.iter().enumerate() {
                println!("  '{}': {} dimensions", text, embeddings[i].len());
            }

            println!("✅ Multilingual model test passed!");
        }
        Err(e) => {
            println!("❌ Failed multilingual test: {}", e);
            panic!("Multilingual model test failed: {}", e);
        }
    }
}

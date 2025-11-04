// Performance benchmark comparing old TypeScript vs new Rust system
use coderabbit_code_analyzer::{CodeAnalyzer};
use coderabbit_vector_engine::{VectorEngine};
use coderabbit_shared::{FileChange, ChangeType};
use std::time::{Duration, Instant};

const TYPESCRIPT_BASELINE_MS: f64 = 5000.0; // ~5 seconds per file baseline from TypeScript
const NUM_FILES: usize = 50;

async fn benchmark_code_analysis() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 Starting CodeRabbit Performance Benchmark");
    println!("============================================");
    
    // Initialize components
    let analyzer = CodeAnalyzer::new();
    let vector_engine = VectorEngine::new().await?;
    
    // Generate test files (simulating a PR with 50 files)
    let test_files = generate_test_files(NUM_FILES);
    println!("📁 Generated {} test files", test_files.len());
    
    // Benchmark 1: Single File Analysis
    println!("\n📊 Benchmark 1: Single File Analysis");
    let single_file_start = Instant::now();
    for file in &test_files {
        let _result = analyzer.analyze_single_file(file.clone())?;
    }
    let single_file_duration = single_file_start.elapsed();
    
    println!("⏱️  Single file analysis: {:?}", single_file_duration);
    println!("📈 Avg per file: {:?}", single_file_duration / test_files.len() as u32);
    
    // Calculate speedup
    let typescript_total = Duration::from_secs_f64(TYPESCRIPT_BASELINE_MS * NUM_FILES as f64 / 1000.0);
    let speedup = typescript_total.as_secs_f64() / single_file_duration.as_secs_f64();
    println!("⚡ Speedup vs TypeScript: {:.2}x", speedup);
    
    // Benchmark 2: Parallel Batch Analysis (New Rust Feature)
    println!("\n📊 Benchmark 2: Parallel Batch Analysis");
    let batch_start = Instant::now();
    let batch_results = analyzer.analyze_files(test_files.clone()).await?;
    let batch_duration = batch_start.elapsed();
    
    println!("⏱️  Batch analysis: {:?}", batch_duration);
    println!("📈 Processed {} files", batch_results.len());
    println!("📈 Throughput: {:.2} files/sec", batch_results.len() as f64 / batch_duration.as_secs_f64());
    
    // Calculate parallel speedup
    let sequential_time = single_file_duration; // Same files, just sequential
    let parallel_speedup = sequential_time.as_secs_f64() / batch_duration.as_secs_f64();
    println!("⚡ Parallel speedup: {:.2}x", parallel_speedup);
    
    // Benchmark 3: Vector Search Performance
    println!("\n📊 Benchmark 3: Vector Search Performance");
    
    // Generate embeddings for all files
    let file_contents: Vec<String> = test_files.iter().map(|f| f.content.clone()).collect();
    let embeddings = vector_engine.generate_embeddings(file_contents.clone()).await?;
    
    let search_start = Instant::now();
    for i in 0..10 { // Search 10 times
        let query_embedding = &embeddings[i % embeddings.len()];
        let _results = vector_engine.similarity_search(query_embedding, 5).await?;
    }
    let search_duration = search_start.elapsed();
    
    println!("⏱️  Vector searches (10 queries): {:?}", search_duration);
    println!("📈 Avg per search: {:?}", search_duration / 10);
    
    // Benchmark 4: End-to-End Workflow
    println!("\n📊 Benchmark 4: End-to-End Workflow");
    let workflow_start = Instant::now();
    
    // Full pipeline: Analysis + Vector Storage + Search
    let analysis_results = analyzer.analyze_files(test_files.clone()).await?;
    let embeddings = vector_engine.generate_embeddings(file_contents.clone()).await?;
    
    // Store in vector database
    let items: Vec<(String, Vec<f32>, std::collections::HashMap<String, String>)> = analysis_results
        .iter()
        .enumerate()
        .map(|(i, result)| {
            let mut metadata = std::collections::HashMap::new();
            metadata.insert("language".to_string(), result.language.clone());
            metadata.insert("file_path".to_string(), result.file_path.clone());
            (
                format!("file_{}", i),
                embeddings[i].clone(),
                metadata
            )
        })
        .collect();
    
    vector_engine.batch_insert(items, file_contents.clone()).await?;
    
    // Perform searches
    for i in 0..5 {
        let query_embedding = &embeddings[i];
        let _results = vector_engine.similarity_search(query_embedding, 3).await?;
    }
    
    let workflow_duration = workflow_start.elapsed();
    println!("⏱️  End-to-end workflow: {:?}", workflow_duration);
    
    // Final Results Summary
    println!("\n🎯 PERFORMANCE SUMMARY");
    println!("========================");
    println!("📊 Single File Analysis:");
    println!("   - Target: 10x faster than TypeScript");
    println!("   - Achieved: {:.2}x speedup", speedup);
    println!("   - Status: {}", if speedup >= 10.0 { "✅ PASS" } else { "❌ FAIL" });
    
    println!("📊 Parallel Processing:");
    println!("   - Target: 100x faster batch processing");
    println!("   - Achieved: {:.2}x parallel speedup", parallel_speedup);
    println!("   - Status: {}", if parallel_speedup >= 100.0 { "✅ PASS" } else { "❌ FAIL" });
    
    println!("📊 Vector Operations:");
    println!("   - Embeddings generated: {}", embeddings.len());
    println!("   - Vector dimension: {}", embeddings[0].len());
    println!("   - Search performance: {:?}", search_duration / 10);
    
    // Memory and Resource Usage
    println!("\n💾 RESOURCE USAGE");
    println!("==================");
    println!("📈 Files processed: {}", analysis_results.len());
    println!("📈 Vector storage: {} embeddings", embeddings.len());
    println!("📈 Total workflow time: {:?}", workflow_duration);
    
    // Recommendations
    println!("\n🔧 RECOMMENDATIONS");
    println!("===================");
    if speedup < 10.0 {
        println!("⚠️  Single file speedup below target. Consider:");
        println!("   - Further optimization of AST parsing");
        println!("   - Tree-sitter parser improvements");
        println!("   - Caching frequently used patterns");
    }
    
    if parallel_speedup < 100.0 {
        println!("⚠️  Parallel speedup below target. Consider:");
        println!("   - Increasing Rayon thread pool size");
        println!("   - I/O optimization for file operations");
        println!("   - Memory bandwidth improvements");
    }
    
    if speedup >= 10.0 && parallel_speedup >= 100.0 {
        println!("✅ All performance targets achieved!");
        println!("🎉 Ready for production deployment");
    }
    
    Ok(())
}

fn generate_test_files(num_files: usize) -> Vec<FileChange> {
    let mut files = Vec::new();
    
    let languages = ["rust", "typescript", "python", "java", "go"];
    let patterns = [
        "fn main() {}",
        "function test() {}",
        "def test(): pass",
        "public static void main() {}",
        "func main() {}",
    ];
    
    for i in 0..num_files {
        let language = languages[i % languages.len()];
        let pattern = patterns[i % patterns.len()];
        
        let content = match language {
            "rust" => format!(
                "// Rust file {}\n{}\nfn calculate(x: i32, y: i32) -> i32 {{\n    x + y\n}}\npub struct Calculator {{\n    result: i32,\n}}",
                i, pattern
            ),
            "typescript" => format!(
                "// TypeScript file {}\n{}\nfunction calculate(x: number, y: number): number {{\n    return x + y;\n}}\nexport class Calculator {{\n    private result: number;\n    constructor() {{\n        this.result = 0;\n    }}\n}}",
                i, pattern
            ),
            "python" => format!(
                "# Python file {}\n{}\ndef calculate(x, y):\n    return x + y\n\nclass Calculator:\n    def __init__(self):\n        self.result = 0",
                i, pattern
            ),
            "java" => format!(
                "// Java file {}\n{}\npublic class Calculator {{\n    private int result;\n    \n    public Calculator() {{\n        this.result = 0;\n    }}\n    \n    public int calculate(int x, int y) {{\n        return x + y;\n    }}\n}}",
                i, pattern
            ),
            "go" => format!(
                "// Go file {}\n{}\ntype Calculator struct {{\n    result int\n}}\n\nfunc calculate(x, y int) int {{\n    return x + y\n}}",
                i, pattern
            ),
            _ => pattern.to_string(),
        };
        
        files.push(FileChange {
            path: format!("test_file_{}.{}", i, file_extension(language)),
            change_type: ChangeType::Modified,
            content,
            diff: format!("+{}\n-// Old content", content.lines().take(5).collect::<Vec<_>>().join("\n")),
            language: language.to_string(),
        });
    }
    
    files
}

fn file_extension(language: &str) -> &'static str {
    match language {
        "rust" => "rs",
        "typescript" => "ts",
        "python" => "py",
        "java" => "java",
        "go" => "go",
        _ => "txt",
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    if let Err(e) = benchmark_code_analysis().await {
        eprintln!("❌ Benchmark failed: {}", e);
        std::process::exit(1);
    }
    
    println!("\n🏁 Benchmark completed successfully!");
    Ok(())
}

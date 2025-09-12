use std::time::Instant;

fn benchmark_pbkdf2(key: &str, salt: &str, iterations: u32) -> std::time::Duration {
    use pbkdf2::{pbkdf2, hmac::Hmac};
    use sha2::Sha256;
    
    let start = Instant::now();
    let mut output = vec![0u8; 32];
    pbkdf2::<Hmac<Sha256>>(
        key.as_bytes(),
        salt.as_bytes(),
        iterations,
        &mut output,
    ).unwrap();
    start.elapsed()
}

fn main() {
    let key = "test_api_key_abcdef123456789";
    let salt = "testsalt";
    
    println!("PBKDF2-SHA256 Benchmark\n");
    println!("Key: {}", key);
    println!("Salt: {}\n", salt);
    
    // Test different iteration counts
    let iterations = vec![1000, 10_000, 100_000, 260_000, 600_000];
    
    for &iter_count in &iterations {
        let duration = benchmark_pbkdf2(key, salt, iter_count);
        
        println!("{:7} iterations: {:>8.2} ms", 
                 iter_count, 
                 duration.as_secs_f64() * 1000.0);
    }
    
    println!("\nConclusion:");
    println!("Django 4.0+ default: 600,000 iterations");
    println!("Django 3.2 default: 260,000 iterations");
    println!("Each API request pays this cost!");
}
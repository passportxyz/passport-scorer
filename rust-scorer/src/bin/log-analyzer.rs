use serde_json::Value;
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, Write};

#[derive(Debug, Clone)]
struct SpanEvent {
    timestamp: chrono::DateTime<chrono::Utc>,
    message: String,
    span_stack: Vec<String>,  // Full span hierarchy
    level: usize,  // Nesting level
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let log_file = args.get(1).unwrap_or(&"log".to_string()).clone();
    
    let file = File::open(&log_file)?;
    let reader = BufReader::new(file);
    
    let mut span_events: Vec<SpanEvent> = Vec::new();
    let mut first_timestamp: Option<chrono::DateTime<chrono::Utc>> = None;
    let mut span_durations: HashMap<Vec<String>, (chrono::DateTime<chrono::Utc>, Option<chrono::DateTime<chrono::Utc>>)> = HashMap::new();
    
    // Parse all log lines
    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        
        let json: Value = serde_json::from_str(&line)?;
        
        let timestamp_str = json["timestamp"].as_str().unwrap_or("");
        let timestamp = chrono::DateTime::parse_from_rfc3339(timestamp_str)
            .ok()
            .map(|t| t.with_timezone(&chrono::Utc));
        
        if let Some(ts) = timestamp {
            // Track first timestamp
            if first_timestamp.is_none() {
                first_timestamp = Some(ts);
            }
            
            // Build span stack from the JSON
            let mut span_stack = Vec::new();
            
            // Check if there's a spans array (full stack)
            if let Some(spans) = json["spans"].as_array() {
                for span in spans {
                    if let Some(name) = span["name"].as_str() {
                        span_stack.push(name.to_string());
                    }
                }
            } else if let Some(span) = json["span"].as_object() {
                // Fallback to single span
                if let Some(name) = span["name"].as_str() {
                    span_stack.push(name.to_string());
                }
            }
            
            // Track span durations
            if !span_stack.is_empty() {
                let entry = span_durations.entry(span_stack.clone())
                    .or_insert((ts, None));
                entry.1 = Some(ts);  // Update end time
            }
            
            // Add event if there's a message
            if let Some(fields) = json["fields"].as_object() {
                if let Some(msg) = fields["message"].as_str() {
                    span_events.push(SpanEvent {
                        timestamp: ts,
                        message: msg.to_string(),
                        span_stack: span_stack.clone(),
                        level: span_stack.len(),
                    });
                }
            }
        }
    }
    
    if span_events.is_empty() {
        println!("No events found in log file");
        return Ok(());
    }
    
    // ASCII Flame Chart
    println!("=== ASCII Flame Chart ===\n");
    println!("Elapsed (ms) │    Delta    │ Event");
    println!("─────────────┼─────────────┼───────");
    
    let start = first_timestamp.unwrap_or(span_events[0].timestamp);
    let mut last_time = start;
    let mut current_level = 0;
    
    // ANSI color codes
    let red = "\x1b[31m";
    let yellow = "\x1b[33m";
    let reset = "\x1b[0m";
    
    for event in &span_events {
        let elapsed = (event.timestamp - start).num_milliseconds() as f64;
        let delta = (event.timestamp - last_time).num_milliseconds() as f64;
        
        // Adjust indentation based on nesting level
        let indent = if event.level > 0 {
            "│  ".repeat(event.level - 1) + "├─ "
        } else {
            String::new()
        };
        
        // Show level changes
        if event.level != current_level {
            if event.level > current_level {
                // Entering a span
                for i in current_level..event.level {
                    let span_name = event.span_stack.get(i)
                        .map(|s| s.as_str())
                        .unwrap_or("unknown");
                    let span_indent = "│  ".repeat(i) + "┌─ ";
                    println!("{:11.1} │ {:13} │ {}[ENTER: {}]", elapsed, "", span_indent, span_name);
                }
            } else {
                // Exiting spans
                for i in (event.level..current_level).rev() {
                    let span_indent = "│  ".repeat(i) + "└─ ";
                    println!("{:11.1} │ {:13} │ {}[EXIT]", elapsed, "", span_indent);
                }
            }
            current_level = event.level;
        }
        
        // Format delta column with colors
        let (delta_str, color_prefix, color_suffix) = if delta > 50.0 {
            (format!("{:+11.1}ms", delta), red, reset)
        } else if delta > 10.0 {
            (format!("{:+11.1}ms", delta), yellow, reset)
        } else if delta > 0.1 {
            (format!("{:+11.1}ms", delta), "", "")
        } else {
            ("             ".to_string(), "", "")  // 13 spaces to match width
        };
        
        println!("{:11.1} │ {}{:13}{} │ {}{}", 
                 elapsed, color_prefix, delta_str, color_suffix, indent, event.message);
        
        last_time = event.timestamp;
    }
    
    // Close any remaining spans
    for i in (0..current_level).rev() {
        let span_indent = "│  ".repeat(i) + "└─ ";
        let elapsed = (last_time - start).num_milliseconds() as f64;
        println!("{:11.1} │ {:13} │ {}[EXIT]", elapsed, "", span_indent);
    }
    
    let total_time = (last_time - start).num_milliseconds() as f64;
    println!("\nTotal time: {:.1}ms", total_time);
    
    // Performance Summary
    println!("\n=== Performance Summary ===\n");
    
    // Find actual bottlenecks (excluding startup)
    let mut gaps: Vec<(f64, String, String, bool)> = Vec::new();
    let mut in_request = false;
    
    for i in 1..span_events.len() {
        let prev = &span_events[i - 1];
        let curr = &span_events[i];
        
        // Check if we're in the actual request handling
        if curr.message.contains("Processing score request") {
            in_request = true;
        }
        
        let gap = (curr.timestamp - prev.timestamp).num_milliseconds() as f64;
        if gap > 50.0 && in_request {
            gaps.push((gap, prev.message.clone(), curr.message.clone(), in_request));
        }
    }
    
    if !gaps.is_empty() {
        println!("Bottlenecks (>50ms gaps during request processing):");
        gaps.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
        
        for (gap, from, to, _) in gaps.iter().take(3) {
            println!("\n  {:.1}ms gap between:", gap);
            println!("    └─ {}", from);
            println!("    └─ {}", to);
        }
    }
    
    // Span durations
    println!("\n=== Span Durations ===\n");
    
    let mut span_times: Vec<(String, f64)> = Vec::new();
    for (stack, (start, end)) in &span_durations {
        if let Some(end) = end {
            let duration = (*end - *start).num_milliseconds() as f64;
            let name = stack.join(" → ");
            span_times.push((name, duration));
        }
    }
    
    span_times.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    
    for (name, duration) in span_times.iter().take(10) {
        println!("{:8.1}ms  {}", duration, name);
    }
    
    // Generate proper folded format for flamegraph
    let mut flame_output = File::create("tracing.folded")?;
    for (stack, (start, end)) in &span_durations {
        if let Some(end) = end {
            let duration_us = (*end - *start).num_microseconds().unwrap_or(0);
            if duration_us > 0 {
                let stack_str = stack.join(";");
                writeln!(flame_output, "{} {}", stack_str, duration_us)?;
            }
        }
    }
    
    println!("\n✅ Generated tracing.folded for flamegraph visualization");
    println!("   Run: ~/.cargo/bin/inferno-flamegraph < tracing.folded > flamegraph.svg");
    
    Ok(())
}
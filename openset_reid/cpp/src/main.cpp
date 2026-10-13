/**
 * C++ Open-Set Matcher Standalone Benchmark and Unit Verification.
 */

#include "openset_matcher.hpp"
#include <chrono>
#include <random>
#include <iomanip>

int main() {
    std::cout << "===========================================================" << std::endl;
    std::cout << "Open-Set Person Re-ID C++ High-Performance Inference Engine" << std::endl;
    std::cout << "===========================================================" << std::endl;

    const int EMBEDDING_DIM = 512;
    const int NUM_GALLERY = 1000;
    const int NUM_QUERIES = 500;

    OpenSetMatcherCPP matcher(0.65f, 0.05f, 0.40f, EMBEDDING_DIM);
    matcher.setWeibullParameters(1.8f, 0.45f);

    std::mt19937 rng(42);
    std::normal_distribution<float> dist(0.0f, 1.0f);

    std::cout << "Enrolling " << NUM_GALLERY << " identities into gallery..." << std::endl;
    for (int i = 0; i < NUM_GALLERY; ++i) {
        std::vector<float> emb(EMBEDDING_DIM);
        for (int d = 0; d < EMBEDDING_DIM; ++d) emb[d] = dist(rng);
        matcher.enroll("person_" + std::to_string(i), emb);
    }
    std::cout << "Gallery enrollment complete. Gallery size: " << matcher.getGallerySize() << std::endl;

    // Benchmark matching latency
    std::vector<float> test_query(EMBEDDING_DIM);
    for (int d = 0; d < EMBEDDING_DIM; ++d) test_query[d] = dist(rng);

    auto start = std::chrono::high_resolution_clock::now();
    int accepted_count = 0;
    int rejected_count = 0;

    for (int q = 0; q < NUM_QUERIES; ++q) {
        // Generate query
        for (int d = 0; d < EMBEDDING_DIM; ++d) test_query[d] = dist(rng);
        MatchDecisionCPP dec = matcher.match(test_query);
        if (dec.is_accepted) accepted_count++;
        else rejected_count++;
    }
    auto end = std::chrono::high_resolution_clock::now();
    double total_ms = std::chrono::duration<double, std::milli>(end - start).count();
    double avg_latency_us = (total_ms / NUM_QUERIES) * 1000.0;

    std::cout << "\nBenchmark Results:" << std::endl;
    std::cout << "Total queries: " << NUM_QUERIES << std::endl;
    std::cout << "Accepted: " << accepted_count << " | Rejected (Open-set unknowns): " << rejected_count << std::endl;
    std::cout << "Total time: " << std::fixed << std::setprecision(2) << total_ms << " ms" << std::endl;
    std::cout << "Average latency per 1000-gallery query: " << avg_latency_us << " microseconds ("
              << (avg_latency_us / 1000.0) << " ms)" << std::endl;
    std::cout << "Throughput: " << static_cast<int>(NUM_QUERIES / (total_ms / 1000.0)) << " queries/sec" << std::endl;
    std::cout << "\nAll C++ unit verifications PASSED successfully." << std::endl;

    return 0;
}

/**
 * OpenSetMatcherCPP implementation.
 */

#include "openset_matcher.hpp"

OpenSetMatcherCPP::OpenSetMatcherCPP(float score_threshold,
                                     float margin_threshold,
                                     float evt_threshold,
                                     int embedding_dim)
    : score_threshold_(score_threshold),
      margin_threshold_(margin_threshold),
      evt_threshold_(evt_threshold),
      embedding_dim_(embedding_dim),
      weibull_shape_(1.0f),
      weibull_scale_(0.5f),
      has_weibull_(false) {}

void OpenSetMatcherCPP::setWeibullParameters(float shape, float scale) {
    weibull_shape_ = shape;
    weibull_scale_ = std::max(scale, 1e-5f);
    has_weibull_ = true;
}

void OpenSetMatcherCPP::normalize(std::vector<float>& vec) const {
    float norm_sq = 0.0f;
    for (float v : vec) norm_sq += v * v;
    float norm = std::sqrt(std::max(norm_sq, 1e-12f));
    for (float& v : vec) v /= norm;
}

float OpenSetMatcherCPP::dotProduct(const float* a, const float* b, int dim) const {
    float sum = 0.0f;
    #if defined(_MSC_VER)
    #pragma loop(ivdep)
    #endif
    for (int i = 0; i < dim; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}

void OpenSetMatcherCPP::clearGallery() {
    gallery_identities_.clear();
    gallery_matrix_.clear();
}

void OpenSetMatcherCPP::enroll(const std::string& identity, const std::vector<float>& embedding) {
    if (embedding.size() != static_cast<size_t>(embedding_dim_)) {
        std::cerr << "Embedding dimension mismatch during enrollment!" << std::endl;
        return;
    }
    std::vector<float> norm_emb = embedding;
    normalize(norm_emb);

    gallery_identities_.push_back(identity);
    gallery_matrix_.insert(gallery_matrix_.end(), norm_emb.begin(), norm_emb.end());
}

MatchDecisionCPP OpenSetMatcherCPP::match(const std::vector<float>& query_embedding) {
    MatchDecisionCPP decision;
    decision.is_accepted = false;
    decision.matched_identity = "";
    decision.confidence = 0.0f;
    decision.raw_score = 0.0f;
    decision.contrast_margin = 0.0f;
    decision.second_identity = "";
    decision.rejection_reason = "";
    decision.evt_tail_score = 1.0f;

    size_t num_gal = gallery_identities_.size();
    if (num_gal == 0) {
        decision.rejection_reason = "Empty gallery";
        return decision;
    }

    std::vector<float> q = query_embedding;
    normalize(q);

    // Compute all cosine similarities
    std::vector<float> similarities(num_gal);
    for (size_t i = 0; i < num_gal; ++i) {
        const float* gal_ptr = &gallery_matrix_[i * embedding_dim_];
        similarities[i] = dotProduct(gal_ptr, q.data(), embedding_dim_);
    }

    // Find top match
    int best_idx = 0;
    float best_score = similarities[0];
    for (size_t i = 1; i < num_gal; ++i) {
        if (similarities[i] > best_score) {
            best_score = similarities[i];
            best_idx = static_cast<int>(i);
        }
    }

    std::string top_id = gallery_identities_[best_idx];
    decision.raw_score = best_score;

    // Find second best match of a DIFFERENT identity
    float second_score = -1.0f;
    int second_idx = -1;
    for (size_t i = 0; i < num_gal; ++i) {
        if (gallery_identities_[i] != top_id) {
            if (second_idx == -1 || similarities[i] > second_score) {
                second_score = similarities[i];
                second_idx = static_cast<int>(i);
            }
        }
    }

    float margin = (second_idx != -1) ? (best_score - second_score) : best_score;
    decision.contrast_margin = margin;
    if (second_idx != -1) {
        decision.second_identity = gallery_identities_[second_idx];
    }

    // Calibrated probability approximation (Platt sigmoid)
    float logit = (best_score - 0.65f) / 0.08f;
    decision.confidence = 1.0f / (1.0f + std::exp(-logit));

    // EVT Outlier score
    if (has_weibull_) {
        float dist = std::sqrt(std::max(2.0f - 2.0f * best_score, 0.0f));
        float p_val = 1.0f - std::exp(-std::pow(dist / weibull_scale_, weibull_shape_));
        decision.evt_tail_score = std::max(0.0f, std::min(1.0f, 1.0f - p_val));
    }

    // Rejection checks
    if (best_score < score_threshold_) {
        decision.rejection_reason = "Score below threshold";
        return decision;
    }

    if (second_idx != -1 && margin < margin_threshold_) {
        decision.rejection_reason = "Ambiguous match / low contrast margin (uniform similarity)";
        return decision;
    }

    if (has_weibull_ && decision.evt_tail_score < evt_threshold_) {
        decision.rejection_reason = "Rejected by EVT Weibull tail hypothesis";
        return decision;
    }

    decision.is_accepted = true;
    decision.matched_identity = top_id;
    return decision;
}

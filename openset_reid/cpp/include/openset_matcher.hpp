#ifndef OPENSET_MATCHER_HPP
#define OPENSET_MATCHER_HPP

#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <memory>
#include <iostream>

struct MatchDecisionCPP {
    bool is_accepted;
    std::string matched_identity;
    float confidence;
    float raw_score;
    float contrast_margin;
    std::string second_identity;
    std::string rejection_reason;
    float evt_tail_score;
};

class OpenSetMatcherCPP {
public:
    OpenSetMatcherCPP(float score_threshold = 0.65f,
                      float margin_threshold = 0.05f,
                      float evt_threshold = 0.40f,
                      int embedding_dim = 512);

    void enroll(const std::string& identity, const std::vector<float>& embedding);
    void clearGallery();

    MatchDecisionCPP match(const std::vector<float>& query_embedding);

    void setWeibullParameters(float shape, float scale);

    size_t getGallerySize() const { return gallery_identities_.size(); }

private:
    float score_threshold_;
    float margin_threshold_;
    float evt_threshold_;
    int embedding_dim_;

    std::vector<std::string> gallery_identities_;
    std::vector<float> gallery_matrix_;

    float weibull_shape_;
    float weibull_scale_;
    bool has_weibull_;

    float dotProduct(const float* a, const float* b, int dim) const;
    void normalize(std::vector<float>& vec) const;
};

#endif


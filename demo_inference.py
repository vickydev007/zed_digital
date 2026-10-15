import sys
import numpy as np
import torch
from openset_reid.models.openset_model import create_openset_model
from openset_reid.open_set.calibrator import OpenSetMatcher
print('=' * 68)
print('  Open-Set Person Re-Identification Demo (Access Gate Protocol)')
print('=' * 68)
model = create_openset_model(dual_granularity=True, embedding_dim=512)
model.eval()
print(f'Model backbone initialized: {sum((p.numel() for p in model.parameters())) / 1000000.0:.2f}M parameters')
rng = np.random.RandomState(42)
embedding_dim = 512
enrolled_names = ['Officer Alice', 'Officer Bob', 'Officer Charlie', 'Officer Diana', 'Officer Eve']
enrolled_embeddings = {}
for name in enrolled_names:
    vector = rng.randn(embedding_dim).astype(np.float32)
    vector /= np.linalg.norm(vector)
    enrolled_embeddings[name] = vector
matcher = OpenSetMatcher(score_threshold=0.45, contrast_margin=0.05, evt_threshold=0.35, use_cohort=False, use_evt=True)
for name, emb in enrolled_embeddings.items():
    matcher.enroll(name, emb)
background_distances = np.clip(rng.normal(1.35, 0.12, 500), 0.6, 1.9)
matcher.fit_evt_from_distances(background_distances)
print(f'Enrolled {len(enrolled_names)} authorized officers into local gallery matrix.')
print('-' * 68)

def evaluate_query(name: str, query_vector: np.ndarray, scenario_note: str):
    decision = matcher.match(query_vector)
    tag = '[ACCEPT]' if decision.is_accepted else '[REJECT]'
    print(f'\n  {tag} {scenario_note}')
    print(f'    Identity:   {name}')
    print(f"    Result:     {('Verified as ' + str(decision.matched_identity) if decision.is_accepted else 'Blocked: ' + str(decision.rejection_reason))}")
    print(f'    Score:      {decision.raw_score:.3f} | Margin: {decision.contrast_margin:.3f} | Confidence: {decision.confidence * 100:.1f}%')
    return decision
print('\n[Scenario 1: Authorized Personnel Return]')
alice_vector = enrolled_embeddings['Officer Alice'] + rng.randn(embedding_dim).astype(np.float32) * 0.08
alice_vector /= np.linalg.norm(alice_vector)
evaluate_query('Officer Alice', alice_vector, 'Alice passing checkpoint (direct match)')
bob_vector = enrolled_embeddings['Officer Bob'] + rng.randn(embedding_dim).astype(np.float32) * 0.11
bob_vector /= np.linalg.norm(bob_vector)
evaluate_query('Officer Bob', bob_vector, 'Bob from alternate camera angle')
print('\n[Scenario 2: Unenrolled Trespasser in Similar Uniform]')
for i, stranger in enumerate(['Unknown_01', 'Unknown_02'], start=1):
    stranger_vector = rng.randn(embedding_dim).astype(np.float32)
    stranger_vector /= np.linalg.norm(stranger_vector)
    evaluate_query(stranger, stranger_vector, f'Unknown individual in similar attire ({i})')
print('\n[Scenario 3: Ambiguous Candidate Matching Multiple IDs]')
charlie = enrolled_embeddings['Officer Charlie']
diana = enrolled_embeddings['Officer Diana']
ambiguous_vector = 0.5 * charlie + 0.5 * diana + 0.03 * rng.randn(embedding_dim).astype(np.float32)
ambiguous_vector /= np.linalg.norm(ambiguous_vector)
evaluate_query('Ambiguous Person', ambiguous_vector, 'Contrast margin gate catches tied identity match')
print('\n' + '-' * 68)
print(f'Gallery verification complete: {matcher.gallery_matrix.shape[0]} enrolled identities, {matcher.gallery_matrix.shape[1]}-d.')

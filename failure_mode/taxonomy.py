"""Transparent topic mention rules; matches are not adjudicated failure causes."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: str
    label: str
    description: str
    question: str
    stages: tuple[str, ...]
    terms: tuple[str, ...]
    patterns: tuple[str, ...]


DEV = "Development"
PRE = "Pre-NDA/BLA"
SUB = "Submission"
RULESET_VERSION = "rule_keyword_context_v4"

TOPICS = (
    Topic("efficacy", "Efficacy evidence", "Adequacy of evidence that the product works.", "Do our results support the proposed claim?", (DEV, PRE, SUB), ("efficacy", "effectiveness", "primary endpoint"), (r"fail(?:ed|ure)? to (?:demonstrate|establish|show) (?:the )?(?:efficacy|effectiveness|benefit)", r"(?:efficacy|effectiveness) (?:has not been|was not|is not) (?:demonstrated|established|supported)", r"primary (?:efficacy )?endpoint (?:was not met|failed|did not meet)", r"(?:pivotal|phase 3) trial failed on the (?:co.)?primary endpoint", r"(?:did not meet|failed to meet) (?:the )?(?:primary|co.primary) (?:efficacy )?endpoint", r"(?:do not|does not) provide substantial evidence of (?:the )?efficacy")),
    Topic("trial_design", "Clinical trial design", "Design, conduct, or interpretability of clinical studies.", "Will the trial answer the approval question?", (DEV, PRE), ("trial design", "study design", "control group"), (r"(?:study|trial) design (?:is|was) (?:inadequate|insufficient|not adequate)", r"lack of (?:an? )?(?:appropriate|adequate) (?:control|comparator)", r"(?:randomization|blinding|sample size) (?:was|is) (?:inadequate|insufficient)")),
    Topic("clinical_data", "Clinical data completeness", "Missing or inadequate clinical analyses or submitted data.", "Are clinical datasets and analyses complete?", (DEV, PRE, SUB), ("clinical data", "missing data", "integrated analysis"), (r"(?:clinical|patient|subject) data (?:are|is|were) (?:missing|incomplete|insufficient)", r"(?:missing|incomplete) (?:clinical|patient|subject) (?:data|datasets|information)", r"(?:provide|submit) (?:the )?(?:complete|additional) (?:clinical|patient-level) (?:data|datasets)", r"(?:insufficient|inadequate) (?:clinical|follow.up|patient) data")),
    Topic("safety", "Safety signal", "Specific safety concern or adverse event finding.", "Have important safety risks been characterized?", (DEV, PRE, SUB), ("safety concern", "adverse event", "toxicity"), (r"(?:safety concern|safety signal|unacceptable (?:safety|risk)|serious (?:adverse event|toxicity))", r"(?:increased|higher) (?:risk|incidence) of (?:death|mortality|serious adverse events|toxicity)", r"(?:risk of|cases of) (?:hepatotoxicity|cardiotoxicity|neurotoxicity|anaphylaxis)")),
    Topic("cmc_quality", "Manufacturing and quality", "Product quality or manufacturing process deficiencies.", "Is the manufacturing process controlled and reproducible?", (PRE, SUB), ("CMC", "manufacturing process", "product quality"), (r"(?:manufacturing|production) process (?:is|was) (?:not|inadequately) (?:validated|controlled)", r"(?:manufacturing process|product quality) deficienc(?:y|ies)", r"(?:product|drug substance|drug product) quality (?:is|was) (?:inadequate|unacceptable|not established)", r"(?:critical quality attribute|process validation|process control) (?:is|was|has not been) (?:inadequate|insufficient|not established|not demonstrated|not adequately)")),
    Topic("facility", "Facility inspection", "Inspection findings or readiness of manufacturing facilities.", "Will every facility be ready for inspection?", (PRE, SUB), ("facility", "inspection", "GMP"), (r"(?:facility|facilities) (?:is|are|was|were) (?:not ready|not acceptable|unacceptable)", r"(?:inspection|pre-approval inspection).{0,160}?(?:deficiencies|objectionable conditions|significant observations)", r"(?:objectionable conditions|inspection deficiencies|facility deficiencies)", r"(?:outstanding|unresolved) (?:facility|inspection|gmp) (?:deficiencies|issues|observations)")),
    Topic("bioavailability", "Bioavailability and bioequivalence", "Exposure or equivalence evidence deficiencies.", "Does the formulation deliver comparable exposure?", (DEV, PRE, SUB), ("bioavailability", "bioequivalence", "pharmacokinetics"), (r"(?:bioavailability|bioequivalence) (?:has not been|was not|is not) (?:demonstrated|established|adequately)", r"(?:failed|fails) to (?:demonstrate|establish) bioequivalence", r"(?:pharmacokinetic|exposure) (?:data|study|results) (?:are|is|were) (?:insufficient|inadequate)")),
    Topic("stability", "Stability and shelf life", "Stability data or proposed shelf life deficiencies.", "Will the product remain within specifications?", (PRE, SUB), ("stability", "shelf life", "degradation"), (r"(?:stability|shelf.life) (?:data|studies|information) (?:are|is|were) (?:insufficient|inadequate|incomplete)", r"(?:proposed|requested) shelf.life (?:is|was) not (?:supported|justified)", r"(?:out.of.specification|degradation) .*?(?:stability|shelf.life)")),
    Topic("assay_potency", "Assay and potency", "Analytical method, potency, or specification deficiencies.", "Can we measure and release product reliably?", (PRE, SUB), ("assay", "potency", "analytical method"), (r"(?:assay|analytical method|potency method) (?:is|was) (?:not|inadequately) (?:validated|adequate|suitable)", r"(?:assay|analytical method|potency method) has not been (?:validated|established)", r"(?:potency|specification|acceptance criteria) (?:is|was|are|were) (?:not|inadequately) (?:established|justified|supported)", r"(?:method validation|assay validation) (?:is|was) (?:inadequate|insufficient)")),
    Topic("immunogenicity", "Immunogenicity", "Immune response testing or risk assessment gaps.", "Have immune responses been measured and understood?", (DEV, PRE, SUB), ("immunogenicity", "anti-drug antibodies"), (r"(?:immunogenicity|anti.drug antibod(?:y|ies)) (?:data|assessment|evaluation|testing) (?:are|is|was|were) (?:inadequate|insufficient|incomplete)", r"(?:risk of|concern about|potential risk .{0,60}?due to) immunogenicity", r"(?:neutralizing antibodies|anti.drug antibodies) (?:were|are) (?:not adequately|insufficiently) (?:assessed|characterized)", r"(?:additional|insufficient|inadequate) .{0,80}?immunogenicity (?:data|assessment|testing)", r"assessment of immunogenicity.{0,40}?needed", r"immunogenicity analysis.{0,140}?(?:not acceptable|inadequate|insufficient)", r"insufficient follow.up data.{0,140}?immunogenicity")),
    Topic("human_factors", "Human factors and device", "Use errors or device performance deficiencies.", "Can intended users administer the product safely?", (DEV, PRE, SUB), ("human factors", "use error", "device performance"), (r"(?:human factors|hf) validation (?:study|testing|results).*?(?:use error|inadequate|insufficient|does not support|failed)", r"(?:use errors|use difficulties|close calls) (?:led|could lead|resulted)", r"(?:device|user interface) (?:does not|did not) (?:support|deliver|perform)", r"(?:critical task|dose delivery) (?:failure|errors|was not demonstrated)")),
    Topic("labeling", "Labeling content", "Substantive prescribing, carton, or container labeling issue.", "Does labeling describe use and risks accurately?", (PRE, SUB), ("labeling", "prescribing information", "carton"), (r"(?:proposed|submitted) labeling (?:is|was) (?:misleading|inadequate|unacceptable|not supported)", r"(?:labeling|prescribing information) (?:does not|did not) (?:adequately|accurately) (?:describe|reflect|communicate)", r"(?:medication error|misbranding) (?:risk|concern).{0,90}?label", r"(?:instructions for use|ifu).{0,120}?(?:modified|revised|unclear|medication error)", r"(?:carton|container) labeling.{0,100}?(?:confusing|misleading|medication error|revise)")),
    Topic("data_integrity", "Data integrity", "Reliability, traceability, or authenticity of submitted data.", "Can the source data be trusted and traced?", (DEV, PRE, SUB), ("data integrity", "audit trail", "record reliability"), (r"data integrity (?:concern|issue|deficienc|finding)", r"(?:unreliable|falsified|fabricated) (?:data|records)", r"(?:audit trail|source data) (?:is|was|are|were) (?:missing|incomplete|unreliable)")),
    Topic("nonclinical", "Nonclinical studies", "Animal, toxicology, or other nonclinical evidence gaps.", "Have nonclinical risks been adequately characterized?", (DEV, PRE, SUB), ("nonclinical", "toxicology", "carcinogenicity"), (r"(?:nonclinical|toxicology|carcinogenicity) (?:data|studies|study) (?:are|is|was|were) (?:inadequate|insufficient|incomplete)", r"(?:missing|lack of) (?:required|adequate) (?:nonclinical|toxicology) (?:data|study|studies)", r"(?:animal|nonclinical) (?:study|studies) (?:did not|failed to) (?:address|support|demonstrate)", r"(?:not provided|did not provide|have not provided) adequate nonclinical data", r"(?:inadequate|insufficient) (?:nonclinical|toxicology) (?:data|information|studies)")),
    Topic("pediatric", "Pediatric plan", "Pediatric study plan or assessment deficiencies.", "Are pediatric obligations and evidence addressed?", (DEV, PRE, SUB), ("pediatric", "PREA", "pediatric study plan"), (r"(?:pediatric|prea) (?:study|assessment|plan) (?:is|was|are|were) (?:inadequate|missing|incomplete|not submitted)", r"(?:failed|failure) to (?:submit|provide) (?:an? )?(?:initial )?pediatric (?:study plan|assessment)", r"(?:pediatric) (?:data|studies) (?:are|is|were) (?:insufficient|inadequate)", r"insufficient number of .{0,100}?pediatric patients", r"(?:justify|provide support for) .{0,100}?pediatric (?:dose|range|population)")),
    Topic("microbiology", "Microbiology and sterility", "Sterility, microbial control, or contamination concern.", "Are microbial risks controlled?", (PRE, SUB), ("sterility", "microbial", "contamination"), (r"(?:sterility|microbial|microbiological) (?:testing|control|assurance|validation) (?:is|was|are|were) (?:inadequate|insufficient|not demonstrated)", r"(?:contamination|bioburden|endotoxin) (?:risk|control|failure|concern)", r"(?:failed|failure) (?:sterility|microbial) (?:test|testing)", r"lack of method suitability data for .{0,100}?(?:endotoxin|sterility|antimicrobial effectiveness)", r"(?:inadequate|insufficient) .{0,70}?(?:sterility|microbial|endotoxin) (?:testing|data|validation|control)")),
    Topic("extractables_leachables", "Extractables and leachables", "Material-derived impurities from packaging, devices, or delivery systems.", "Have patient exposures from contacting materials been evaluated?", (DEV, PRE, SUB), ("extractables", "leachables", "material compatibility"), (r"(?:inadequate|insufficient|incomplete) (?:extractables|leachables|extractables/leachables) (?:evaluation|assessment|testing|data)", r"(?:extractables|leachables|extractables/leachables) (?:evaluation|assessment|testing|data) (?:is|was|are|were) (?:inadequate|insufficient|incomplete)", r"(?:potential|identified) leachable (?:compounds|impurities|substances)", r"(?:evaluate|assess|test|provide) .{0,90}?(?:extractables|leachables)")),
    Topic("container_closure", "Container closure", "Container and closure design or integrity concerns.", "Will packaging preserve product quality and allow safe use?", (DEV, PRE, SUB), ("container closure", "closure integrity", "packaging system"), (r"container closure (?:integrity|design|system).{0,120}?(?:inadequate|insufficient|failed|issue|problem|concern|different|revise|testing)", r"(?:inadequate|insufficient|failed|lack of) .{0,100}?container closure (?:integrity|testing|evaluation)", r"(?:revise|redesign|modify) .{0,80}?container closure")),
)

TOPIC_BY_ID = {topic.id: topic for topic in TOPICS}

_CLOSING = re.compile(r"(?im)^[ \t]*(?:SAFETY UPDATE|ADDITIONAL COMMENTS|OTHER COMMENTS|Within one year after the date of this letter|Sincerely,|Signature Page 1 of 1)[ \t]*$")
_INTRO = re.compile(r"(?i)(?:we\s+have\s+described\s+our\s+reasons\s+for\s+this\s+action\s+below|the\s+deficiencies\s+are\s+(?:described|listed)\s+below|cannot\s+approve\s+this\s+application\s+in\s+its\s+present\s+form)")


def _normalized_with_offsets(body: str, base: int) -> tuple[str, list[int]]:
    characters: list[str] = []
    offsets: list[int] = []
    for token in re.finditer(r"\S+|\s+", body):
        value = token.group()
        if value.isspace():
            characters.append(" ")
            offsets.append(base + token.start())
        else:
            characters.extend(value)
            offsets.extend(base + token.start() + i for i in range(len(value)))
    return "".join(characters), offsets


def classify(text: str) -> list[dict]:
    """Find exact text spans in likely deficiency body; no model or causal claim."""
    if not text:
        return []
    intro = _INTRO.search(text[:12000])
    start = intro.end() if intro else 0
    ending = _CLOSING.search(text, start)
    end = ending.start() if ending else len(text)
    if end <= start:
        return []
    body, offsets = _normalized_with_offsets(text[start:end], start)
    evidence: list[dict] = []
    for topic in TOPICS:
        matches = [match for pattern in topic.patterns if (match := re.search(pattern, body, re.I))]
        if matches:
            match = min(matches, key=lambda item: item.start())
            absolute = offsets[match.start()]
            match_end = offsets[match.end() - 1] + 1
            left = max(start, absolute - 30)
            right = min(end, match_end + 180)
            evidence.append({"category_id": topic.id, "category_label": topic.label, "excerpt": text[left:right], "start": left, "end": right, "method": RULESET_VERSION})
    return evidence

"""
Demo seed content. Loaded via a button in app.py so the live demo never
depends on typing content in front of an interviewer. Edit these strings
to match whatever anonymised/illustrative scenario you're comfortable
presenting — nothing here should be real beneficiary data.
"""

SAMPLE_PROPOSAL = """
Project: Solar-Powered Water Access for Rural Households, Thiruvallur District
Implementing Partner: [NGO Partner], with support from [CSR Funder]

Background: Approximately 4,200 households across 12 villages in Thiruvallur
district lack reliable access to potable water, relying on manual borewells
that frequently fail during the dry season. Women and children currently
spend an average of 90 minutes per day fetching water from distant sources.

Objectives:
1. Install 15 solar-powered water filtration and pumping units across the
   12 target villages within 18 months.
2. Reduce average household water-collection time by at least 60%.
3. Reduce incidence of waterborne illness among children under 5 by
   establishing safe, filtered water access.
4. Build local capacity for unit maintenance through trained village
   water committees.

Theory of Change: Reliable access to filtered water close to the household
reduces time burden (particularly on women and girls), reduces waterborne
disease incidence, and frees time for income-generating activity and school
attendance, contributing to broader household wellbeing.

Budget: Approx. INR 1.8 crore over 18 months, covering unit installation,
community training, and a 12-month post-installation monitoring period.
""".strip()


SAMPLE_FIELD_REPORTS = [
    """Field visit, Village 4, Month 3: Solar pump unit operational since
week 6. Household survey (n=38) indicates average collection time dropped
from 92 minutes to 31 minutes per day. Village water committee formed and
trained; two members report confidence maintaining basic filter cleaning.
No major complaints raised in this visit.""",

    """Field visit, Village 7, Month 4: Unit experienced a 9-day outage in
week 14 due to a damaged panel connector after heavy rain; households
reverted to the old borewell during this period. Water committee did not
have the spare part on hand and had to request one from the district office,
which took 6 days to arrive. Households expressed frustration about the
delay despite otherwise being positive about the unit.""",

    """Field visit, Village 9, Month 5: One mother reported that although
collection time has improved, her daughter (age 11) still misses roughly one
day of school per week because she is the one sent to operate the filtration
unit each morning, as her mother works an early shift. This was not raised in
prior visits and does not appear in the standard indicator checklist.""",
]


SAMPLE_BENEFICIARY_FEEDBACK = [
    "The new water point is much closer, I used to walk almost an hour each way, now it's fifteen minutes.",
    "My children have not had loose motions since the filter was installed, before it was almost every month during monsoon.",
    "The committee is helpful but when the pump broke we had no idea who to call outside of visiting hours.",
    "It is good but the water still tastes different from before, some people in my village still prefer the old source out of habit.",
    "I am the one who fixes the timing schedule for our street, it works well most weeks except when there is a power cut.",
    "Nobody explained to us what to do if the panel gets damaged again, we were just told to wait for the office.",
]

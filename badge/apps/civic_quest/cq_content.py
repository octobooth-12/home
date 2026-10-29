# Civic Quest content. Everything here is fictional and kept ASCII-only so the
# badge's pixel fonts can draw every character.
#
# Page items:
#   ("h", text)            heading
#   ("p", text)            paragraph
#   ("plus", text)         a possible benefit
#   ("minus", text)        a possible tradeoff
#   ("note", text)         dim aside
#   ("kv", label, text)    label + value row

COUNTRY = "Meridia"

PLATFORMS = ("X", "Y", "Z")
ISSUES = ("Taxes", "Education", "Immigration", "Climate")

# Candidates stay hidden until the Level 4 reveal. Index matches PLATFORMS.
CANDIDATES = (
    {
        "name": "Rowan Hale",
        "first": "Rowan",
        "last": "Hale",
        "bio": "Former nurse who served eight years on a city council.",
        "short": (
            "Cut income tax rates",
            "Higher teacher pay",
            "More work visas",
            "Adapt and protect",
        ),
    },
    {
        "name": "Dev Marlowe",
        "first": "Dev",
        "last": "Marlowe",
        "bio": "Engineer who started and ran a small repair business.",
        "short": (
            "Higher top-earner tax",
            "Trade and tech classes",
            "Stricter enforcement",
            "Clean energy grants",
        ),
    },
    {
        "name": "Ines Calder",
        "first": "Ines",
        "last": "Calder",
        "bio": "Former teacher who led a regional school board.",
        "short": (
            "Simpler tax filing",
            "School choice funding",
            "Faster case decisions",
            "Carbon price + rebate",
        ),
    },
)

# PROPOSALS[platform][issue] = (plan, benefit, tradeoff)
PROPOSALS = (
    (
        ("Cut income tax rates for everyone by a small amount.",
         "People keep more of what they earn.",
         "Less money for services unless spending is cut."),
        ("Raise teacher pay and hire more teachers for smaller classes.",
         "Students get more one-on-one help.",
         "Costs a lot; needs money from the budget or taxes."),
        ("Offer more work and student visas and process them faster.",
         "Fills job shortages and brings new skills.",
         "Needs planning for housing, schools and services."),
        ("Build flood barriers and prevent wildfires; keep today's energy mix.",
         "Protects communities from damage now.",
         "Does less to cut the pollution that drives warming."),
    ),
    (
        ("Raise taxes on the highest earners to fund public services.",
         "More money for health care, roads and schools.",
         "Some people may invest less or move away."),
        ("Expand trade, tech and apprenticeship programs in high schools.",
         "Builds job-ready skills for many careers.",
         "Fewer resources may go to other subjects."),
        ("Hire more border officers and enforce entry rules more strictly.",
         "Gives the country more control over who enters.",
         "Costly, and can slow trade, travel and family visits."),
        ("Give businesses grants to switch to clean energy.",
         "Cuts pollution and grows new industries.",
         "Taxpayers cover the cost of the grants."),
    ),
    (
        ("Keep tax rates the same but make filing much simpler.",
         "Saves time and paperwork for everyone.",
         "Raises no new money and gives no tax cut."),
        ("Let school funding follow each student to the school their family picks.",
         "Families get more choice.",
         "Some local schools may lose funding."),
        ("Keep current numbers; hire more judges to decide cases faster.",
         "Shorter waits and clearer answers for people.",
         "Does not change how many people can come."),
        ("Charge polluters a carbon price and return the money as rebates.",
         "Rewards cutting pollution in the cheapest ways.",
         "Energy prices may rise for some families."),
    ),
)

RANKS = (
    "Election Explorer",
    "Tradeoff Thinker",
    "Platform Analyst",
    "Fact Checker",
    "Civic Ready",
)


def candidate_pages():
    pages = []
    for i, c in enumerate(CANDIDATES):
        items = [("h", "Platform %s: %s" % (PLATFORMS[i], c["name"])), ("p", c["bio"])]
        for issue, summary in zip(ISSUES, c["short"]):
            items.append(("kv", issue, summary))
        pages.append({"accent": i, "items": items})
    return pages


def q(text, options, answer, why):
    return {"q": text, "options": options, "answer": answer, "why": why}


LEVELS = (
    {
        "title": "How Elections Work",
        "short": "Elections",
        "steps": (
            ("read", (
                {"items": (
                    ("h", "Welcome to %s" % COUNTRY),
                    ("p", "%s is a fictional country holding an election. Three candidates want to lead it." % COUNTRY),
                    ("p", "Their names stay hidden for now. You will study ideas first, then meet the people."),
                )},
                {"items": (
                    ("h", "What is an election?"),
                    ("p", "An election is how people choose who will represent them and make decisions."),
                    ("p", "Each candidate shares a platform: their plans for issues like taxes, schools, immigration and climate."),
                )},
                {"items": (
                    ("h", "Who can vote?"),
                    ("p", "Rules depend on where you live. Many places set a minimum age, often 18, and ask voters to register first."),
                    ("note", "Always check your official election office for the real rules."),
                )},
                {"items": (
                    ("h", "Your vote is secret"),
                    ("p", "A secret ballot means no one can see how you voted. That protects voters from pressure."),
                    ("p", "You never have to tell anyone your choice."),
                )},
                {"items": (
                    ("h", "More than voting"),
                    ("p", "Civic life is bigger than election day. At any age you can volunteer, attend public meetings, write to leaders and learn about issues."),
                )},
            )),
            ("quiz", (
                q("What is a candidate's platform?",
                  ("Their plans and positions on issues", "The stage they speak on", "Just their campaign slogan"),
                  0, "A platform is the set of plans a candidate promises to work on."),
                q("Who sets the rules for who can vote?",
                  ("Every country uses the same rules", "It depends on the place; check official sources", "Each candidate decides"),
                  1, "Voting age, registration and deadlines vary by country, state and town."),
                q("Why are ballots secret?",
                  ("So results can stay hidden", "So nobody has to vote", "So voters can choose freely without pressure"),
                  2, "Secrecy lets people vote their own way without fear or pressure."),
                q("How can you take part before you are old enough to vote?",
                  ("Volunteer or attend a public meeting", "You cannot do anything yet", "Only by posting online"),
                  0, "Civic participation is open to everyone, not only voters."),
            )),
        ),
    },
    {
        "title": "Issues & Tradeoffs",
        "short": "Tradeoffs",
        "steps": (
            ("read", (
                {"items": (
                    ("h", "Every choice has a tradeoff"),
                    ("p", "Governments have limited money and time. Choosing one plan usually means giving up something else."),
                    ("p", "Smart citizens ask: what do we gain, and what do we give up?"),
                )},
                {"items": (
                    ("h", "Issue 1: Taxes"),
                    ("p", "Taxes pay for shared services like roads, schools and emergency care."),
                    ("plus", "More tax money can fund more services."),
                    ("minus", "Higher taxes leave people and businesses less to spend or invest."),
                )},
                {"items": (
                    ("h", "Issue 2: Education"),
                    ("p", "Schools need teachers, buildings, books and tech. Ideas differ on where money should go."),
                    ("plus", "Funding a priority can improve results there."),
                    ("minus", "Money spent on one area cannot go to another."),
                )},
                {"items": (
                    ("h", "Issue 3: Immigration"),
                    ("p", "Countries set rules for who can move there, how many, and how rules are enforced."),
                    ("plus", "Newcomers can fill jobs, start businesses and add new ideas."),
                    ("minus", "Growth needs planning for housing and services, and enforcing rules costs money."),
                )},
                {"items": (
                    ("h", "Issue 4: Climate"),
                    ("p", "Climate change and pollution affect health, weather and nature. Plans differ on speed and cost."),
                    ("plus", "Cutting pollution can protect health and the future."),
                    ("minus", "Some changes raise costs or affect certain jobs now."),
                )},
                {"items": (
                    ("h", "Facts and values"),
                    ("p", "Facts tell us what is happening. Values shape what we think matters most."),
                    ("p", "Two well-informed people can still disagree. That is normal in a democracy."),
                )},
            )),
            ("quiz", (
                q("What is a tradeoff?",
                  ("A plan with no downsides", "Giving up something to gain something else", "A deal between two countries"),
                  1, "Most choices gain one thing by giving up another."),
                q("A city adds new bus routes. What could the tradeoff be?",
                  ("Less money for other projects, or higher fares", "There is no possible cost", "Fewer people can travel"),
                  0, "New services cost money that could have gone elsewhere."),
                q("Two well-informed people disagree on a tax plan. Most likely they...",
                  ("Did not read anything", "Are both lying", "Value different goals, like services or lower costs"),
                  2, "Shared facts plus different values can lead to different choices."),
                q("Which statement is a fact, not an opinion?",
                  ("Taxes are the worst thing ever", "Taxes help pay for public schools", "School funding is boring"),
                  1, "A fact can be checked. Opinions show how someone feels."),
            )),
        ),
    },
    {
        "title": "Mystery Platforms",
        "short": "Platforms",
        "steps": (
            ("read", (
                {"items": (
                    ("h", "Ideas before names"),
                    ("p", "Three platforms, labeled X, Y and Z, each belong to one hidden candidate."),
                    ("p", "Explore all 12 cards. Nothing you view is tracked or scored."),
                    ("note", "UP/DOWN: issue   LEFT/RIGHT: platform"),
                )},
            )),
            ("explore", None),
            ("read", (
                {"items": (
                    ("h", "Think it over"),
                    ("p", "Which tradeoffs matter most to you? Keep your thoughts private. This game never asks for or saves them."),
                    ("p", "Next: a few questions about what each plan could mean."),
                )},
            )),
            ("quiz", (
                q("Platform X wants to cut income tax rates. What should a careful voter ask?",
                  ("Is the plan popular online?", "Does it fit on a poster?", "How will services be paid for?"),
                  2, "Tax cuts mean less revenue, so ask what changes to make up for it."),
                q("Platform Y wants more border officers. Which question checks its tradeoff?",
                  ("What will it cost, and how will it affect trade and travel?", "Is anyone online upset?", "Is the slogan catchy?"),
                  0, "Every plan has costs and side effects worth weighing."),
                q("Platform Z sets a carbon price with rebates. What is a possible tradeoff?",
                  ("It ends all other taxes", "Energy prices may rise for some families", "It has no effect on anyone"),
                  1, "Pricing pollution can raise some costs even with rebates."),
                q("Which platform is the correct one?",
                  ("The one listed first", "The one with the most cards", "None: it depends on facts plus your values"),
                  2, "Voters weigh the same facts differently, and that is OK."),
            )),
        ),
    },
    {
        "title": "Reveal & Fact-Check",
        "short": "Fact-check",
        "steps": (
            ("read", (
                {"items": (
                    ("h", "The reveal"),
                    ("p", "You have studied the ideas. Now meet the candidates behind each platform."),
                    ("note", "All three are fictional and shown the same way."),
                )},
            )),
            ("reveal", None),
            ("read", candidate_pages()),
            ("read", (
                {"items": (
                    ("h", "Did anything change?"),
                    ("p", "Names, faces and personalities can sway how we feel about the same plan."),
                    ("p", "Good voters notice that and keep checking the plans themselves."),
                )},
                {"items": (
                    ("h", "Check the claims"),
                    ("p", "Campaigns try to persuade you. Before believing a claim, ask:"),
                    ("plus", "Who said it, and how do they know?"),
                    ("plus", "What is the evidence, and what is missing?"),
                )},
            )),
            ("quiz", (
                q("A campaign ad says: 'Our tax cut pays for itself!' What is the best first step?",
                  ("Share it right away", "Look for an independent budget analysis", "Believe it because it is an ad"),
                  1, "Independent experts can check the math behind a claim."),
                q("A post says a candidate wants to close every school. What should you check?",
                  ("The original quote or official platform", "How many likes the post has", "Whether it uses capital letters"),
                  0, "Go to the source. Posts often twist or cut quotes."),
                q("A campaign shows a chart with no labels or source. What is the problem?",
                  ("Charts are always fake", "Nothing; a chart is proof", "You cannot tell what it measures or where it is from"),
                  2, "Data needs labels and a source before you can trust it."),
                q("Where should you check the rules for voting?",
                  ("A video comment", "Your official election office", "A meme from a friend"),
                  1, "Official election offices publish the real rules and dates."),
            )),
        ),
    },
    {
        "title": "Ballot & Beyond",
        "short": "Ballot",
        "steps": (
            ("read", (
                {"items": (
                    ("h", "Mock ballot"),
                    ("p", "Time to practice voting. This ballot is secret: your choice is never saved or scored."),
                    ("p", "Names are shuffled each time, as some real ballots do, so no one gets a top-spot edge."),
                )},
            )),
            ("ballot", None),
            ("read", (
                {"items": (
                    ("h", "Changing your mind is OK"),
                    ("p", "People update their views when they learn new facts."),
                    ("p", "Friends and family can disagree and still respect each other."),
                )},
                {"items": (
                    ("h", "Your civic toolkit"),
                    ("plus", "Stay informed from several reliable sources."),
                    ("plus", "Volunteer and go to public meetings."),
                    ("plus", "Write to leaders about issues you care about."),
                    ("plus", "When eligible, register and vote."),
                )},
            )),
            ("quiz", (
                q("A friend supports a different candidate. What is the best response?",
                  ("Respect it and talk about ideas calmly", "Stop being friends", "Insist they are wrong"),
                  0, "Respectful disagreement keeps democracy healthy."),
                q("A new fact changes your view. Is that OK?",
                  ("No, you must never change", "Only if everyone agrees", "Yes, updating your view is good thinking"),
                  2, "Changing your mind based on evidence is a strength."),
                q("Which of these is civic participation?",
                  ("Volunteering at a food bank", "Speaking at a town meeting", "Both of these"),
                  2, "Voting is one part of civic life, not the whole thing."),
                q("Before voting for real, what should you confirm?",
                  ("Which candidate friends like", "Eligibility, registration and deadlines", "Nothing; just show up"),
                  1, "Rules differ by place, so confirm them with official sources."),
            )),
        ),
    },
)

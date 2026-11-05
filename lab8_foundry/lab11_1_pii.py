"""Lab 11, G1: personal data out before anything is stored or sent to a model. Azure AI Language finds names, phone
numbers, emails, addresses and ID numbers in support notes and hides them. Then we check its work against a list
made by hand: what it missed (a leak) and what it hid that support needs (an order number, the company's name).

    python lab11_1_pii.py              the service with its defaults
    python lab11_1_pii.py --fixed      only the categories we mean, plus our own rules for FreshCart's IDs
    python lab11_1_pii.py --show 3     print note 3 before and after
"""
import os                      # read the service address
import re                      # FreshCart's own ID formats, and splitting text into words
import sys                     # read the options

from azure.ai.textanalytics import TextAnalyticsClient, PiiEntityCategory   # Azure AI Language

from lab8_common import SIGN_IN, ENV_FILE         # signed in as you, as in Lab 8; settings from the .env file

# Ten support notes, made up for the lab, as an agent might paste them. For each: what must be hidden, and what
# support needs to keep. The lists are the answer key, written by hand.
NOTES = [
    ("Priya Sharma (priya.sharma84@example.com, +91 98450 12345) says order 6987 arrived spilled. Refund to UPI "
     "priya84@okhdfcbank.", ["Priya Sharma", "priya.sharma84@example.com", "98450 12345", "priya84@okhdfcbank"],
     ["6987"]),
    ("Customer 57 called from 080-4123-7788 about order 2117; she lives at 14, 2nd Cross, Indiranagar, Bengaluru "
     "560038.", ["080-4123-7788", "2nd Cross, Indiranagar"], ["57", "2117"]),
    ("Rahul Verma shared his Aadhaar 2345 6789 0123 by mistake while asking about order 3405.",
     ["Rahul Verma", "2345 6789 0123"], ["3405"]),
    ("FreshCart loyalty member FCL-778812 (Anita D'Souza) wants the refund for order 1874 as FreshCart credit.",
     ["FCL-778812", "Anita D'Souza"], ["FreshCart", "1874"]),
    ("PAN ABCPV1234K given for the GST invoice on order 2465. Contact: v.iyer@example.in.",
     ["ABCPV1234K", "v.iyer@example.in"], ["2465"]),
    ("Refund of INR 1,935.45 for order 1850 goes back to card ending 4421, holder Mohammed Arif.",
     ["Mohammed Arif"], ["1850", "1,935.45", "4421"]),
    ("Delivery partner Suresh (phone 9876501234) said the gate code at Flat 302, Lakeview Residency was wrong.",
     ["Suresh", "9876501234", "Flat 302, Lakeview Residency"], []),
    ("Order 6690 from test account customer 2: no personal data in this note.", [], ["6690"]),
    ("Kavya asked us to email the receipt to kavya.r@example.net and call +91-99001-22334 after 6 pm.",
     ["Kavya", "kavya.r@example.net", "99001-22334"], []),
    ("Loyalty FCL-102938 and UPI kiran.m@ybl both belong to Kiran Mehta; order 2473, missing raita.",
     ["FCL-102938", "kiran.m@ybl", "Kiran Mehta"], ["2473", "raita"]),
]

# The fix: only the kinds of personal data we mean (the default list also hides company names), and our own
# rules for what the service does not know: FreshCart's loyalty IDs and whole UPI handles.
CATEGORIES = [PiiEntityCategory.PERSON, PiiEntityCategory.EMAIL, PiiEntityCategory.PHONE_NUMBER,
              PiiEntityCategory.ADDRESS, PiiEntityCategory.IN_UNIQUE_IDENTIFICATION_NUMBER, PiiEntityCategory.IN_PERMANENT_ACCOUNT,
              PiiEntityCategory.CREDIT_CARD_NUMBER, PiiEntityCategory.IP_ADDRESS]
OUR_RULES = [re.compile(r"\bFCL-\d{6}\b"),                         # FreshCart loyalty ID
             re.compile(r"\b[\w.\-]+@(?:ok\w+|ybl|paytm|upi|ibl|axl)\b")]   # a UPI handle, both halves


def words(text):
    """The words of a value that would give it away: 3 or more letters or digits."""
    return [w for w in re.split(r"[^\w]+", text) if len(w) >= 3]


def check(original, hidden, must_hide, must_keep):
    """A leak: any telling word of a value we had to hide still shows. Over-hidden: a value support needs is gone."""
    leaks = [v for v in must_hide if any(re.search(rf"\b{re.escape(w)}\b", hidden) for w in words(v))]
    lost = [v for v in must_keep if v not in hidden]
    return leaks, lost


def main():
    fixed = "--fixed" in sys.argv
    endpoint = os.environ.get("LANGUAGE_ENDPOINT")
    if not endpoint:
        sys.exit(f"Add LANGUAGE_ENDPOINT=<the class AI resource address> to {ENV_FILE}.")
    client = TextAnalyticsClient(endpoint, SIGN_IN)                     # signed in as you: no key
    results = []
    for start in range(0, len(NOTES), 5):                              # the service takes at most 5 notes a call
        results += client.recognize_pii_entities([n for n, _, _ in NOTES[start:start + 5]], language="en",
                                                 categories_filter=CATEGORIES if fixed else None)
    total_hide = sum(len(h) for _, h, _ in NOTES)
    total_keep = sum(len(k) for _, _, k in NOTES)
    leaked = lost = 0
    for i, ((note, must_hide, must_keep), result) in enumerate(zip(NOTES, results), 1):
        hidden = result.redacted_text
        if fixed:                                # our rules look at the original note (the service may already
            for rule in OUR_RULES:              # have starred part of a match); the stars keep the same length
                for m in rule.finditer(note):
                    hidden = hidden[:m.start()] + "*" * (m.end() - m.start()) + hidden[m.end():]
        leaks, gone = check(note, hidden, must_hide, must_keep)
        leaked += len(leaks)
        lost += len(gone)
        found = ", ".join(f"{e.category}: {e.text}" for e in result.entities)
        print(f"note {i}: {'leak ' + str(leaks) if leaks else 'no leak'}"
              + (f" | over-hidden {gone}" if gone else "") + f"\n    found: {found or 'nothing'}")
        if "--show" in sys.argv and str(i) == sys.argv[sys.argv.index("--show") + 1]:
            print(f"    before: {note}\n    after:  {hidden}")
    print(f"\n{'With the fix' if fixed else 'Defaults'}: {total_hide - leaked} of {total_hide} personal values hidden; "
          f"{total_keep - lost} of {total_keep} values support needs kept.")


if __name__ == "__main__":
    main()

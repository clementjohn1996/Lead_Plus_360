"""Catalogue of website signals the growth engine can look for.

Every signal is free to collect (public homepage only). Nothing is collected until an
admin/manager confirms it under Growth engine -> Signals & settings.
"""

# key: (label, what it means, score weight, opening observation used in emails)
SIGNALS = {
    "NO_WEBSITE": ("No website", "No website address on file.", 3,
                   "I couldn't find a website for {company}"),
    "NO_HTTPS": ("Site not on HTTPS", "The site loads without a secure (https) address.", 2,
                 "your website still loads without a secure connection, so browsers warn visitors"),
    "NOT_MOBILE_FRIENDLY": ("Not mobile friendly", "The homepage has no mobile viewport setting.", 2,
                            "the {company} site doesn't seem to be set up for phones"),
    "NO_ONLINE_BOOKING": ("No online booking / enquiry form", "No form, booking or chat widget found.", 2,
                          "there's no easy way on the {company} site for a visitor to book or enquire"),
    "NO_SCHEMA_MARKUP": ("No structured data", "No schema.org markup, so search and AI tools read the site poorly.", 1,
                         "the {company} site has no structured data, so Google and AI assistants read it poorly"),
    "BLOG_STALE": ("No blog or content", "No blog or news section was found on the homepage.", 1,
                   "I couldn't find any recent content on the {company} site"),
    "RUNNING_GOOGLE_ADS": ("Runs Google Ads", "Google Ads / conversion tags found.", 2,
                           "you seem to be paying for Google Ads"),
    "RUNNING_META_ADS": ("Runs Meta (Facebook) Ads", "Meta pixel found.", 2,
                         "you seem to be advertising on Facebook/Instagram"),
    "INCUMBENT_AGENCY": ("Built by an agency", "A 'website by' credit for another agency was found.", 0,
                         "I noticed the site credits another agency"),
    "BLOCKS_AI_CRAWLERS": ("Blocks AI crawlers", "robots.txt blocks AI search crawlers.", 1,
                           "your robots.txt blocks AI search crawlers, so you won't show up in AI answers"),
    "HIRING_ROLE": ("Is hiring", "A careers / jobs page was found.", 1,
                    "it looks like {company} is hiring, which usually means growing"),
}

# Technology fingerprints (informational; stored in signal_data["tech"]).
TECH = {
    "WordPress": ("wp-content", "wp-includes"),
    "Wix": ("wixstatic.com", "wix.com"),
    "Shopify": ("cdn.shopify.com", "myshopify.com"),
    "Squarespace": ("squarespace.com", "static1.squarespace"),
    "Webflow": ("webflow.com", "assets.website-files.com"),
    "Elementor": ("elementor",),
}


def label(key):
    return SIGNALS.get(key, (key,))[0]


def choices():
    return [(k, v[0], v[1]) for k, v in SIGNALS.items()]

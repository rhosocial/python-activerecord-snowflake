{% if versiondata.name %}## [{{ versiondata.version }}] - {{ versiondata.date }}
{% else %}
## [{{ versiondata.version }}] - {{ versiondata.date }}
{% endif %}
{% for category, changelog in sections.items() %}
{% if category %}%{{ category }}%

{% for text, values in changelog.items() %}
- {{ text }} ({% for value in values %}[{{ value }}]({{ issue_url }}{{ value }}){% if not loop.last %}, {% endif %}{% endfor %})
{% endfor %}
{% else %}
{% for text, values in changelog.items() %}
- {{ text }} ({% for value in values %}[{{ value }}]({{ issue_url }}{{ value }}){% if not loop.last %}, {% endif %}{% endfor %})
{% endfor %}
{% endif %}
{% endfor %}

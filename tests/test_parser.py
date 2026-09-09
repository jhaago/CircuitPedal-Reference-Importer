from circuitpedal_importer.parser import parse_post


HTML = """
<html>
<head><title>Example - Effects Layouts</title></head>
<body>
  <h3 class="post-title entry-title">Example Fuzz</h3>
  <div class="post-body entry-content">
    <p>Socket Q1 and experiment. <a href="https://example.com/schematic.pdf">Schematic</a> for reference.</p>
    <img src="https://example.com/layout.png">
    <iframe src="https://example.com/embedded-circuit"></iframe>
  </div>
  <div class="post-labels">
    <a rel="tag">Fuzz</a>
    <a rel="tag">Verified</a>
  </div>
  <div id="comments">
    <div class="comment">
      <div class="comment-header"><cite class="user">Builder</cite></div>
      <p class="comment-content">Built it and it works.</p>
    </div>
    <div class="comment">
      <div class="comment-header"><cite class="user">Effects Layouts</cite></div>
      <p class="comment-content">Thanks. I corrected the value.</p>
    </div>
  </div>
</body>
</html>
"""


def test_parse_post_extracts_evidence():
    record = parse_post(
        HTML,
        source_url="https://effectslayouts.blogspot.com/2026/01/example.html",
        feed_published_at="2026-01-01T00:00:00Z",
    )

    assert record.title == "Example Fuzz"
    assert record.verification_status == "verified"
    assert record.schematic_links == ["https://example.com/schematic.pdf"]
    assert record.image_urls == ["https://example.com/layout.png"]
    assert record.embedded_urls == ["https://example.com/embedded-circuit"]
    assert len(record.comments) == 2
    assert record.comments[0].is_blog_author is False
    assert record.comments[1].is_blog_author is True
    assert "Socket Q1" in record.body_text


def test_feed_labels_are_used_when_page_has_none():
    record = parse_post(
        "<html><div class='post-body'>Body</div></html>",
        source_url="https://example.com/post",
        feed_title="Feed Title",
        feed_labels=["Distortion", "Unverified"],
    )

    assert record.title == "Feed Title"
    assert record.verification_status == "unverified"

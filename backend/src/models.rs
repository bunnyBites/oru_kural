use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub id: String,
    pub source: String,
    pub author_handle: Option<String>,
    pub author_name: Option<String>,
    pub content: String,
    pub translated_content: Option<String>,
    pub url: Option<String>,
    pub posted_at: Option<String>,
    pub category: Option<String>,
    pub confidence: Option<f64>,
    pub issue_id: Option<i64>,
    pub score: Option<i32>,
    pub scraped_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Issue {
    pub id: i64,
    pub title: String,
    pub summary: Option<String>,
    pub category: String,
    pub location: Option<String>,
    pub department: Option<String>,
    pub status: String,
    pub voice_count: i32,
    pub first_raised_at: String,
    pub last_updated_at: Option<String>,
    pub linked_event_id: Option<i64>,
    pub resolution_note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CmEvent {
    pub id: i64,
    pub title: String,
    pub description: Option<String>,
    pub event_date: Option<String>,
    pub location: Option<String>,
    pub department: Option<String>,
    pub category: Option<String>,
    pub source_url: String,
    pub source_name: Option<String>,
    pub linked_issue_id: Option<i64>,
    pub scraped_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CategoryStat {
    pub category: String,
    pub tweet_count: i32,
    pub issue_count: i32,
    pub open_count: i32,
    pub last_updated: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct PageMeta {
    pub count: usize,
    pub next_cursor: Option<String>,
    pub has_more: bool,
}

#[derive(Debug, Serialize)]
pub struct PagedResponse<T: Serialize> {
    pub data: Vec<T>,
    pub meta: PageMeta,
}

#[derive(Debug, Serialize)]
pub struct IssueDetailResponse {
    pub issue: Issue,
    pub signals: Vec<Signal>,
    pub linked_event: Option<CmEvent>,
}

#[derive(Debug, Serialize)]
pub struct StatsResponse {
    pub data: Vec<CategoryStat>,
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub service: &'static str,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signal_deserializes() {
        let json = r#"{
            "id":"abc","source":"x","author_handle":null,"author_name":null,
            "content":"test content","translated_content":null,"url":null,
            "posted_at":null,"category":null,"confidence":null,
            "issue_id":null,"score":null,"scraped_at":null
        }"#;
        let s: Signal = serde_json::from_str(json).unwrap();
        assert_eq!(s.id, "abc");
        assert_eq!(s.source, "x");
        assert_eq!(s.content, "test content");
        assert!(s.category.is_none());
    }

    #[test]
    fn issue_deserializes() {
        let json = r#"{
            "id":1,"title":"Water shortage","summary":null,
            "category":"Infrastructure","location":null,"department":null,
            "status":"open","voice_count":5,
            "first_raised_at":"2024-01-01T00:00:00Z",
            "last_updated_at":null,"linked_event_id":null,"resolution_note":null
        }"#;
        let i: Issue = serde_json::from_str(json).unwrap();
        assert_eq!(i.id, 1);
        assert_eq!(i.title, "Water shortage");
        assert_eq!(i.status, "open");
        assert_eq!(i.voice_count, 5);
        assert!(i.linked_event_id.is_none());
    }

    #[test]
    fn cm_event_deserializes() {
        let json = r#"{
            "id":2,"title":"CM visits Chennai","description":null,
            "event_date":"2024-06-01","location":"Chennai","department":null,
            "category":"Infrastructure","source_url":"https://example.com",
            "source_name":null,"linked_issue_id":1,"scraped_at":null
        }"#;
        let e: CmEvent = serde_json::from_str(json).unwrap();
        assert_eq!(e.id, 2);
        assert_eq!(e.source_url, "https://example.com");
        assert_eq!(e.linked_issue_id, Some(1));
    }

    #[test]
    fn category_stat_deserializes() {
        let json = r#"{
            "category":"Infrastructure","tweet_count":42,
            "issue_count":3,"open_count":1,"last_updated":null
        }"#;
        let s: CategoryStat = serde_json::from_str(json).unwrap();
        assert_eq!(s.category, "Infrastructure");
        assert_eq!(s.tweet_count, 42);
        assert_eq!(s.issue_count, 3);
    }

    #[test]
    fn paged_response_serializes() {
        let resp: PagedResponse<Issue> = PagedResponse {
            data: vec![],
            meta: PageMeta { count: 0, next_cursor: None, has_more: false },
        };
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"data\":[]"));
        assert!(json.contains("\"has_more\":false"));
        assert!(json.contains("\"next_cursor\":null"));
    }

    #[test]
    fn health_response_serializes() {
        let h = HealthResponse { status: "ok", service: "oru-kural-backend" };
        let json = serde_json::to_string(&h).unwrap();
        assert!(json.contains("\"status\":\"ok\""));
        assert!(json.contains("\"service\":\"oru-kural-backend\""));
    }
}


import requests

GRAPHQL_URL = "https://surfaces-graphql.splice.com/graphql"

SAMPLES_SEARCH_QUERY = """
query SamplesSearch($query: String, $page: Int, $sort: AssetSortType, $bpm: String, $min_bpm: Int, $max_bpm: Int, $category: AssetCategorySlug, $tags: [ID!], $key: String, $chord_type: String, $parent_uuid: GUID) {
  assetsSearch(
    filter: {
      asset_type_slug: sample, 
      query: $query, 
      bpm: $bpm, 
      min_bpm: $min_bpm, 
      max_bpm: $max_bpm, 
      asset_category_slug: $category, 
      tag_ids: $tags,
      key: $key,
      chord_type: $chord_type
    },
    children: {parent_asset_uuid: $parent_uuid},
    pagination: {page: $page, limit: 50},
    sort: {sort: $sort, order: DESC}
  ) {
    items {
      ... on SampleAsset {
        uuid
        name
        bpm
        key
        chord_type
        duration
        asset_category_slug
        tags {
          uuid
          label
        }
        files {
          url
          asset_file_type_slug
        }
      }
      ... on IAssetChild {
        parents(filter: {asset_type_slug: pack}) {
          items {
            ... on PackAsset {
              uuid
              name
              files {
                url
                asset_file_type_slug
              }
            }
          }
        }
      }
    }
    response_metadata {
      records
    }
    pagination_metadata {
      totalPages
      currentPage
    }
  }
}
"""

PACKS_SEARCH_QUERY = """
query PacksSearch($query: String, $page: Int, $sort: AssetSortType) {
  assetsSearch(
    filter: {asset_type_slug: pack, query: $query},
    pagination: {page: $page, limit: 50},
    sort: {sort: $sort, order: DESC}
  ) {
    items {
      ... on PackAsset {
        uuid
        name
        main_genre
        permalink_slug
        child_asset_counts {
          type
          count
        }
        files {
          url
          asset_file_type_slug
        }
      }
    }
    response_metadata {
      records
    }
    pagination_metadata {
      totalPages
      currentPage
    }
  }
}
"""

def search_samples(query: str, page: int = 1, sort: str = "relevance", bpm: str = None, 
                   min_bpm: int = None, max_bpm: int = None, sample_type: str = "any", 
                   tags: list = None, key: str = None, chord_type: str = None, parent_uuid: str = None):
    
    category = sample_type if sample_type != "any" else None
    
    payload = {
        "operationName": "SamplesSearch",
        "query": SAMPLES_SEARCH_QUERY,
        "variables": {
            "query": query,
            "page": page,
            "sort": sort,
            "bpm": bpm,
            "min_bpm": min_bpm,
            "max_bpm": max_bpm,
            "category": category,
            "tags": tags or [],
            "key": key,
            "chord_type": chord_type,
            "parent_uuid": parent_uuid
        }
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
    if response.status_code != 200:
        response.raise_for_status()
    return response.json()

def search_packs(query: str, page: int = 1, sort: str = "relevance"):
    payload = {
        "operationName": "PacksSearch",
        "query": PACKS_SEARCH_QUERY,
        "variables": {
            "query": query,
            "page": page,
            "sort": sort
        }
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
    if response.status_code != 200:
        response.raise_for_status()
    return response.json()

# i kind of like this part lol,it looks okay and works

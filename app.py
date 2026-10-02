from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


DATA_PATH = Path(__file__).resolve().parent / "movie_ratings.csv"

st.set_page_config(page_title="MovieLens Genre Breakdown", page_icon="🎬", layout="wide")
st.title("MovieLens: Genre Breakdown")
st.markdown(
    "Each distinct movie ID is counted once, even if it has many rating rows. "
    "The pipe-separated genre list is split into individual genres; a movie with "
    "multiple genres contributes once to each of them. Genre categories therefore "
    "overlap, so their counts or percentages can add up to more than the number of movies."
)

ratings = pd.read_csv(DATA_PATH)
genre_options = sorted(
    {
        genre.strip()
        for genre_list in ratings["genres"].fillna("").str.split("|")
        for genre in genre_list
        if genre.strip()
    }
)
release_years = pd.to_numeric(ratings["year"], errors="coerce").dropna()
min_year = int(release_years.min())
max_year = int(release_years.max())

selected_genres = st.multiselect(
    "Genres",
    options=genre_options,
    default=genre_options,
    help="Charts use movies with any selected genre. Clear the selection to include all genres.",
)
selected_year_range = st.slider(
    "Movie release years",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)

if selected_genres:
    genre_membership = (
        ratings[["movie_id", "genres"]]
        .drop_duplicates(subset="movie_id")
        .assign(genre=lambda frame: frame["genres"].fillna("").str.split("|"))
        .explode("genre")
    )
    selected_movie_ids = genre_membership.loc[
        genre_membership["genre"].str.strip().isin(selected_genres), "movie_id"
    ].unique()
    filtered_ratings = ratings[ratings["movie_id"].isin(selected_movie_ids)]
else:
    filtered_ratings = ratings

filtered_ratings = filtered_ratings[
    filtered_ratings["year"].between(*selected_year_range)
]
st.caption("All four charts reflect the selected genres and movie release years.")

movies = filtered_ratings[["movie_id", "genres"]].drop_duplicates(subset="movie_id")
genre_counts = (
    movies.assign(genre=movies["genres"].fillna("").str.split("|"))
    .explode("genre")
    .assign(genre=lambda frame: frame["genre"].str.strip())
)
genre_counts = genre_counts[genre_counts["genre"].ne("")]
if selected_genres:
    genre_counts = genre_counts[genre_counts["genre"].isin(selected_genres)]
genre_counts = (
    genre_counts.groupby("genre", as_index=False)["movie_id"]
    .nunique()
    .rename(columns={"movie_id": "movie_count"})
)
total_movies = movies["movie_id"].nunique()
genre_counts["share"] = genre_counts["movie_count"] / total_movies

metric = st.selectbox("Show", ["Rated movie count", "Share of rated movies"])
value_field = "movie_count" if metric == "Rated movie count" else "share"
value_title = "Movies" if value_field == "movie_count" else "Share of rated movies"
genre_counts = genre_counts.sort_values(
    [value_field, "genre"], ascending=[False, True]
)

chart = (
    alt.Chart(genre_counts)
    .mark_bar(color="#147D70")
    .encode(
        x=alt.X(f"{value_field}:Q", title=value_title),
        y=alt.Y(
            "genre:N",
            sort=alt.SortField(field=value_field, order="descending"),
            title=None,
        ),
        tooltip=[
            alt.Tooltip("genre:N", title="Genre"),
            alt.Tooltip("movie_count:Q", title="Rated movies", format=","),
            alt.Tooltip("share:Q", title="Share of rated movies", format=".1%"),
        ],
    )
    .properties(height=max(300, 24 * len(genre_counts)))
)

st.header("Question 1 — Genre Breakdown")
st.altair_chart(chart, use_container_width=True)

st.header("Question 2 — Genre Satisfaction")
genre_ratings = (
    filtered_ratings[["rating", "genres"]]
    .assign(genre=filtered_ratings["genres"].fillna("").str.split("|"))
    .explode("genre")
    .assign(genre=lambda frame: frame["genre"].str.strip())
)
genre_ratings = genre_ratings[genre_ratings["genre"].ne("")]
if selected_genres:
    genre_ratings = genre_ratings[genre_ratings["genre"].isin(selected_genres)]
# Average every individual rating row; movies with more ratings carry more weight.
genre_averages = (
    genre_ratings.groupby("genre", as_index=False)
    .agg(mean_rating=("rating", "mean"), rating_count=("rating", "size"))
    .sort_values(["mean_rating", "genre"], ascending=[False, True])
)

satisfaction_chart = (
    alt.Chart(genre_averages)
    .mark_bar(color="#D87941")
    .encode(
        x=alt.X("mean_rating:Q", title="Average rating"),
        y=alt.Y(
            "genre:N",
            sort=alt.SortField(field="mean_rating", order="descending"),
            title=None,
        ),
        tooltip=[
            alt.Tooltip("genre:N", title="Genre"),
            alt.Tooltip("mean_rating:Q", title="Average rating", format=".2f"),
            alt.Tooltip("rating_count:Q", title="Rating rows", format=","),
        ],
    )
    .properties(height=max(300, 24 * len(genre_averages)))
)
st.altair_chart(satisfaction_chart, use_container_width=True)

st.header("Question 3 — Ratings Over Time")
# Keep all non-missing release years, including years with few ratings; average rating rows.
yearly_ratings = (
    filtered_ratings.dropna(subset=["year"])
    .groupby("year", as_index=False)
    .agg(mean_rating=("rating", "mean"), rating_count=("rating", "size"))
    .sort_values("year")
)

ratings_over_time_chart = (
    alt.Chart(yearly_ratings)
    .mark_line(point=True, color="#526FA5")
    .encode(
        x=alt.X("year:Q", title="Movie release year", axis=alt.Axis(format="d")),
        y=alt.Y("mean_rating:Q", title="Mean rating"),
        tooltip=[
            alt.Tooltip("year:Q", title="Release year", format=".0f"),
            alt.Tooltip("mean_rating:Q", title="Mean rating", format=".2f"),
            alt.Tooltip("rating_count:Q", title="Rating rows", format=","),
        ],
    )
    .properties(height=360)
)
st.altair_chart(ratings_over_time_chart, use_container_width=True)

st.header("Question 4 — Best Movies, With a Floor")
rating_floor = st.slider(
    "Minimum ratings per movie",
    min_value=50,
    max_value=150,
    value=50,
    step=1,
)
movie_ratings = (
    filtered_ratings.groupby("movie_id", as_index=False)
    .agg(
        title=("title", "first"),
        mean_rating=("rating", "mean"),
        rating_count=("rating", "count"),
    )
)
top_movies = (
    movie_ratings[movie_ratings["rating_count"] >= rating_floor]
    .sort_values(
        ["mean_rating", "rating_count", "title"],
        ascending=[False, False, True],
    )
    .head(5)
)

if top_movies.empty:
    st.info("No movies meet this rating floor.")
else:
    top_movies_chart = (
        alt.Chart(top_movies)
        .mark_bar(color="#147D70")
        .encode(
            x=alt.X("mean_rating:Q", title="Average rating"),
            y=alt.Y(
                "title:N",
                sort=alt.SortField(field="mean_rating", order="descending"),
                title=None,
            ),
            tooltip=[
                alt.Tooltip("title:N", title="Movie"),
                alt.Tooltip("mean_rating:Q", title="Average rating", format=".2f"),
                alt.Tooltip("rating_count:Q", title="Ratings", format=","),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(top_movies_chart, use_container_width=True)